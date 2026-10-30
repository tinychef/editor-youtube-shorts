"""Person matte + face/head tracking in one pass over the cut video (MediaPipe, CPU).

The matte is stored at reduced resolution as a lossless gray video (matte.mkv); the renderer upsamples
and refines it against the full-resolution frame. track.json holds per-frame face and head positions,
smoothed per shot so jump cuts don't drift.
"""
import os
import time
import urllib.request
from pathlib import Path

import cv2
import numpy as np

from .util import CACHE, log, write_json
from .videoio import Reader, Writer

MODELS = {
    "selfie": "image_segmenter/selfie_segmenter/float16/latest/selfie_segmenter.tflite",
    "multiclass": "image_segmenter/selfie_multiclass_256x256/float32/latest/selfie_multiclass_256x256.tflite",
    "face": "face_detector/blaze_face_short_range/float16/latest/blaze_face_short_range.tflite",
}


def model_path(name):
    p = CACHE / "models" / MODELS[name].split("/")[-1]
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        log(f"descargando modelo {p.name}…")
        urllib.request.urlretrieve("https://storage.googleapis.com/mediapipe-models/" + MODELS[name], p)
    return str(p)


def guided(I, p, r, eps):
    """He et al. guided filter (gray guide): snaps a coarse mask to the image's real edges."""
    k = (r, r)
    mI, mp = cv2.boxFilter(I, -1, k), cv2.boxFilter(p, -1, k)
    cov = cv2.boxFilter(I * p, -1, k) - mI * mp
    var = cv2.boxFilter(I * I, -1, k) - mI * mI
    a = cov / (var + eps)
    b = mp - a * mI
    return cv2.boxFilter(a, -1, k) * I + cv2.boxFilter(b, -1, k)


class Segmenter:
    def __init__(self, quality="hq"):
        try:
            import mediapipe as mp
            from mediapipe.tasks.python import vision
            from mediapipe.tasks.python.core.base_options import BaseOptions
        except (ImportError, OSError) as e:
            raise SystemExit(f"MediaPipe no se pudo cargar ({e}). En Linux instala libegl1: sudo apt install libegl1")
        self.mp = mp
        mk = lambda m: vision.ImageSegmenter.create_from_options(vision.ImageSegmenterOptions(
            base_options=BaseOptions(model_asset_path=model_path(m)), output_confidence_masks=True))
        # hq: 6-class model (hair/skin/clothes) — far fewer background leaks; fast: binary selfie model (~10x faster)
        self.selfie = mk("selfie") if quality in ("fast", "max") else None
        self.multi = mk("multiclass") if quality in ("hq", "max") else None
        self.face = vision.FaceDetector.create_from_options(vision.FaceDetectorOptions(
            base_options=BaseOptions(model_asset_path=model_path("face")), min_detection_confidence=0.5))

    def _img(self, rgb):
        return self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))

    def person(self, rgb):
        img = self._img(rgb)
        p = None
        if self.selfie is not None:
            p = np.squeeze(self.selfie.segment(img).confidence_masks[0].numpy_view()).astype(np.float32)
        if self.multi is not None:
            bg = np.squeeze(self.multi.segment(img).confidence_masks[0].numpy_view()).astype(np.float32)
            p = 1.0 - bg if p is None else np.maximum(p, 1.0 - bg)
        return p

    def close(self):
        for t in (self.selfie, self.multi, self.face):
            if t is not None:
                try:
                    t.close()
                except Exception:
                    pass

    def faces(self, rgb):
        r = self.face.detect(self._img(rgb))
        h, w = rgb.shape[:2]
        out = []
        for d in r.detections:
            b = d.bounding_box
            out.append((b.origin_x / w, b.origin_y / h, b.width / w, b.height / h, d.categories[0].score))
        return out


def clean(p):
    """Keep the main silhouette, drop stray blobs, fill holes (dark shirts on dark walls)."""
    m = (p > 0.5).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
    if n <= 1:
        return p * 0.0
    big = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
    keep = np.zeros_like(m)
    amax = st[big, cv2.CC_STAT_AREA]
    for i in range(1, n):
        if i == big or st[i, cv2.CC_STAT_AREA] > 0.25 * amax:
            keep[lab == i] = 1
    # fill holes: anything not reachable from the border through background is inside the person
    inv = (1 - keep).astype(np.uint8)
    h, w = inv.shape
    ff = inv.copy()
    mask = np.zeros((h + 2, w + 2), np.uint8)
    for x in range(0, w, 8):
        for y in (0, h - 1):
            if ff[y, x] == 1:
                cv2.floodFill(ff, mask, (x, y), 2)
    for y in range(0, h, 8):
        for x in (0, w - 1):
            if ff[y, x] == 1:
                cv2.floodFill(ff, mask, (x, y), 2)
    holes = (ff == 1).astype(np.float32)
    region = cv2.dilate(keep, np.ones((9, 9), np.uint8)).astype(np.float32)
    return np.maximum(p * region, holes)


def analysis_size(w, h, long_side=1024):
    s = long_side / max(w, h)
    return int(round(w * s / 2)) * 2, int(round(h * s / 2)) * 2


def _part(job):
    """Matte + tracking for frames [a, b) (one process; a part start behaves like a cut)."""
    cut_path, (aw, ah), fps, a, b, shots, out_path, quality, verbose = job
    seg = Segmenter(quality)
    rd = Reader(cut_path, (aw, ah), "rgb24", start=a / fps)
    wr = Writer(out_path, (aw, ah), fps, fmt="gray", codec="ffv1")
    face, head, span = [], [], []
    prev_p = prev_g = None
    t0 = time.time()
    for i in range(a, b):
        rgb = rd.read()
        if rgb is None:
            break
        g = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255
        p = seg.person(rgb)
        p = np.clip(guided(g, p, 9, 2e-3), 0, 1)
        if prev_p is not None and i not in shots:
            motion = cv2.GaussianBlur(np.abs(g - prev_g), (0, 0), 3)
            k = 0.55 + 0.4 * np.clip((motion - 0.015) / 0.06, 0, 1)
            p = k * p + (1 - k) * prev_p
        p = clean(p)
        prev_p, prev_g = p, g
        wr.write((p * 255 + 0.5).astype(np.uint8))
        fs = seg.faces(rgb) if (i - a) % 2 == 0 or not face else None
        if fs is not None:
            fs = sorted(fs, key=lambda f: f[2] * f[3], reverse=True)
            face.append(fs[0][:4] if fs else None)
        else:
            face.append(face[-1])
        rows = np.nonzero((p > 0.5).sum(axis=1) > 0.035 * aw)[0]
        cols = np.nonzero((p > 0.5).sum(axis=0) > 0.02 * ah)[0]
        head.append(rows[0] / ah if len(rows) else None)
        span.append((cols[0] / aw, cols[-1] / aw) if len(cols) else None)
        if verbose and (i - a) % 150 == 149:
            log(f"recorte: {100 * (i - a + 1) / (b - a):.0f}% del primer bloque ({(i - a + 1) / (time.time() - t0):.1f} cps por proceso)")
    rd.close()
    wr.close()
    seg.close()
    return face, head, span


def analyze(cut_path, size, fps, shot_starts, out_dir, quality="hq", frames=None, jobs=0):
    """matte.mkv (gray, analysis resolution) + track.json, split across processes."""
    import multiprocessing as mp
    from .util import run
    aw, ah = analysis_size(*size)
    shots = sorted(set(int(round(t * fps)) for t in shot_starts))
    n = frames or int(round(float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                       str(cut_path)]).stdout) * fps))
    jobs = jobs or min(4, os.cpu_count() or 2)
    per = max(60, -(-n // jobs))
    t0 = time.time()
    tasks = [(str(cut_path), (aw, ah), fps, a, min(n, a + per), shots, str(out_dir / f"matte_{k:02d}.mkv"), quality, k == 0)
             for k, a in enumerate(range(0, n, per))]
    if len(tasks) == 1:
        res = [_part(tasks[0])]
    else:
        with mp.get_context("spawn").Pool(len(tasks)) as pool:
            res = pool.map(_part, tasks)
    lst = out_dir / "matte_parts.txt"
    lst.write_text("".join(f"file '{Path(t[6]).name}'\n" for t in tasks))
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out_dir / "matte.mkv")])
    for t in tasks:
        Path(t[6]).unlink(missing_ok=True)
    lst.unlink(missing_ok=True)
    face = [x for r in res for x in r[0]]
    head = [x for r in res for x in r[1]]
    span = [x for r in res for x in r[2]]
    track = smooth_track(face, head, span, len(face), fps, shots + [t[3] for t in tasks])
    write_json(out_dir / "track.json", {"fps": fps, "size": [aw, ah], **track})
    log(f"recorte y seguimiento: {len(face)} cuadros en {time.time() - t0:.0f} s ({len(tasks)} procesos)")
    return len(face)


def _fill(vals, default):
    v = np.array([np.nan if x is None else x for x in vals], dtype=np.float64)
    if np.all(np.isnan(v)):
        return np.full(len(v), default)
    idx = np.arange(len(v))
    ok = ~np.isnan(v)
    return np.interp(idx, idx[ok], v[ok])


def _smooth(v, shots, win):
    out = v.copy()
    bounds = sorted(set([0, *[s for s in shots if 0 < s < len(v)], len(v)]))
    for a, b in zip(bounds[:-1], bounds[1:]):
        seg = v[a:b]
        k = min(win, len(seg))
        if k > 2:
            pad = np.pad(seg, (k // 2, k - 1 - k // 2), mode="edge")
            out[a:b] = np.convolve(pad, np.ones(k) / k, mode="valid")
    return out


def smooth_track(face, head, span, n, fps, shots):
    win = max(3, int(fps * 0.6))
    fx = _fill([f[0] + f[2] / 2 if f else None for f in face], 0.5)
    fy = _fill([f[1] + f[3] / 2 if f else None for f in face], 0.38)
    fh = _fill([f[3] if f else None for f in face], 0.18)
    ht = _fill(head, 0.12)
    sl = _fill([s[0] if s else None for s in span], 0.1)
    sr = _fill([s[1] if s else None for s in span], 0.9)
    r = lambda a: [round(float(x), 4) for x in _smooth(a, shots, win)]
    return {"face_x": r(fx), "face_y": r(fy), "face_h": r(fh), "head_top": r(ht), "left": r(sl), "right": r(sr)}
