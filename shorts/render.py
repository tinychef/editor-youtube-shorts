"""Stage 2 · render: plan.json + work/<name>/ → 1080x1920 MP4 (parallel chunks, then audio + mux)."""
import json
import multiprocessing as mp
import os
import shutil
import time
from pathlib import Path

import numpy as np

from . import audio, captions, layout, timeline
from .compose import Composer, Overlay
from .overlay import EMPTY, SAME, Pages, write_html
from .themes import Backdrop, hex_rgb, theme
from .util import W as CW, H as CH, at, log, read_json, run, slug, span, write_json
from .videoio import Reader, Writer


def setup(plan_path, draft=False):
    plan_path = Path(plan_path).resolve()
    plan = json.loads(plan_path.read_text(encoding="utf8"))
    base = plan_path.parent
    wd = Path(plan.get("work", "")).expanduser()
    wd = wd if wd.is_absolute() else (base / wd)
    if not (wd / "meta.json").exists():
        raise SystemExit(f"No encuentro {wd / 'meta.json'}: corre primero `python -m shorts prepare <video>`")
    meta, track = read_json(wd / "meta.json"), read_json(wd / "track.json")
    words = captions.apply_fixes(read_json(wd / "words.json"), plan.get("fixes"), (plan.get("captions") or {}).get("replace"))
    dur = meta["frames"] / meta["fps"]
    th = theme(plan.get("theme"))
    segs = layout.resolve(plan.get("layout"), words, dur, CW, CH, default=plan.get("default_layout", "sticker"))
    items, mutes = timeline.build(plan.get("overlays"), words, dur, segs, base, plan.get("logo_style", "tile"))
    cap_style = dict(plan.get("captions") or {})
    mutes += captions.mute_spans(cap_style.pop("mute", []), words, dur)
    caps = captions.build(words, cap_style, dur, mutes)
    zooms = []
    for z in plan.get("zooms", []):
        t0, t1 = span(z, words, dur, default_dur=0.9)
        zooms.append({"t0": t0, "t1": t1, "scale": float(z.get("scale", 1.15))})
    place_captions(caps, segs, track, meta, th, zooms, plan, items)
    tl = {"W": CW, "H": CH, "fps": meta["fps"], "items": items, "captions": caps,
          "layout": [{"t0": s["t0"], "t1": s["t1"], "zone": s["zone"]} for s in segs]}
    rdir = wd / "render"
    rdir.mkdir(exist_ok=True)
    html = {"under": write_html(tl, th, "under", rdir / "under.html"), "over": write_html(tl, th, "over", rdir / "over.html")}
    out = plan.get("output") or f"out/{slug(Path(meta['source']).stem)}.mp4"
    out = Path(out) if Path(out).is_absolute() else base / out
    return {"plan": plan, "plan_path": str(plan_path), "base": str(base), "work": str(wd), "meta": meta, "track": track,
            "words": words, "dur": dur, "theme": th, "segs": segs, "zooms": zooms, "html": {k: str(v) for k, v in html.items()},
            "draft": draft, "out": str(out), "fps": meta["fps"], "frames": meta["frames"]}


SAFE_BOTTOM = 1530     # lower than this, YouTube's title/buttons cover the captions


def place_captions(caps, segs, track, meta, th, zooms, plan, items=()):
    """Give every caption chunk a height that keeps it off the face: below the chin if that stays inside the
    Shorts safe area, else above the head when no card occupies that space, else as low as safely possible."""
    sp = layout.Speaker(segs, track, tuple(meta["size"]), CW, CH, meta["fps"], meta["shots"], th, zooms,
                        plan.get("cut_zoom"))
    fixed = caps["style"].get("y")
    n = len(track["face_h"])
    for ch in caps["chunks"]:
        i = min(n - 1, int(ch["t0"] * meta["fps"]))
        seg = next((s for s in reversed(segs) if s["t0"] <= ch["t0"] + 1e-6), segs[0])
        y = fixed or seg["zone"]["cap"]
        half = 50 if sum(len(w["w"]) + 1 for w in ch["words"]) <= 18 else 95
        if not fixed and seg["zone"].get("capOn") == "speaker":
            P = sp.params(i)
            if P["vis"] > 0.5:
                fh = track["face_h"][i] * meta["size"][1] * P["scale"]
                cy = P["ay"] + P["dy"]
                top, chin = cy - 0.62 * fh, cy + 0.66 * fh
                if y + half > top and y - half < chin:
                    below, above = chin + half + 26, top - half - 30
                    busy = any(it["place"] in ("stack", "header", "title") and it["t0"] <= ch["t1"] and it["t1"] > ch["t0"]
                               for it in items)
                    if below <= SAFE_BOTTOM:
                        y = below
                    elif above >= 260 and (not busy or above - half > seg["zone"]["top"][1]):
                        y = above
                    else:
                        y = SAFE_BOTTOM
        ch["y"] = round(y)


def _scale(ctx):
    return 0.5 if ctx["draft"] else 1.0


class Frames:
    """Everything one process needs to compose frames [a, b)."""

    def __init__(self, ctx, a):
        self.ctx = ctx
        k = _scale(ctx)
        self.k = k
        self.W, self.H = int(CW * k), int(CH * k)
        fps = ctx["fps"]
        sw, sh = ctx["meta"]["size"]
        self.rs = (max(2, int(sw * k) // 2 * 2), max(2, int(sh * k) // 2 * 2)) if ctx["draft"] else (sw, sh)
        ms = ctx["track"]["size"]
        self.vid = Reader(Path(ctx["work"]) / "cut.mkv", self.rs, "rgb24", start=a / fps)
        self.mat = Reader(Path(ctx["work"]) / "matte.mkv", tuple(ms), "gray", start=a / fps)
        self.sp = layout.Speaker(ctx["segs"], ctx["track"], (sw, sh), CW, CH, fps, ctx["meta"]["shots"], ctx["theme"],
                                 ctx["zooms"], ctx["plan"].get("cut_zoom"))
        self.comp = Composer(self.W, self.H, Backdrop(ctx["theme"], self.W, self.H, k), ctx["theme"], (sw, sh), tuple(ms), k)
        self.pages = Pages(ctx["html"], scale=k)
        self.under, self.over = Overlay(), Overlay()
        pr = ctx["plan"].get("progress")
        self.prog = None
        if pr:
            c = pr if isinstance(pr, str) else ctx["theme"]["vars"]["--accent"]
            self.prog = np.array(hex_rgb(c), np.float32) / 255
        self.last_v = self.last_m = None

    def render(self, i):
        v, m = self.vid.read(), self.mat.read()
        v = self.last_v if v is None else v
        m = self.last_m if m is None else m
        self.last_v, self.last_m = v, m
        t = i / self.ctx["fps"]
        ov = self.pages.frame(t)
        for layer, slot in (("under", self.under), ("over", self.over)):
            r = ov[layer]
            if r is EMPTY or (isinstance(r, str) and r == EMPTY):
                slot.clear()
            elif not (isinstance(r, str) and r == SAME):
                slot.set(r)
        P = self.sp.params(i)
        prog = (t / self.ctx["dur"]) if self.prog is not None else None
        return self.comp.frame(v, m, P, self.under, self.over, prog, self.prog, t)

    def close(self):
        self.vid.close()
        self.mat.close()
        self.pages.close()


def _chunk(job):
    ctx, a, b, out, idx = job
    t = time.time()
    fr = Frames(ctx, a)
    k = _scale(ctx)
    wr = Writer(out, (int(CW * k), int(CH * k)), ctx["fps"], crf=16 if not ctx["draft"] else 23,
                preset="medium" if not ctx["draft"] else "veryfast")
    for i in range(a, b):
        wr.write(fr.render(i))
        if idx == 0 and (i - a) % 60 == 59:
            done = (i - a + 1) / (b - a)
            log(f"render: {100 * done:.0f}% del primer bloque · {(i - a + 1) / (time.time() - t):.1f} cps por proceso")
    wr.close()
    fr.close()
    return out


def render(plan_path, out=None, draft=False, t_from=None, t_to=None, frames=None, jobs=0):
    t_start = time.time()
    ctx = setup(plan_path, draft)
    fps, nfr = ctx["fps"], ctx["frames"]
    if out:
        ctx["out"] = str(Path(out).resolve())
    if frames:
        return stills(ctx, [at(x.strip(), ctx["words"], ctx["dur"]) for x in str(frames).split(",")])
    a = int(round((t_from or 0) * fps))
    b = min(nfr, int(round(t_to * fps)) if t_to else nfr)
    jobs = jobs or min(4, os.cpu_count() or 2)
    n = b - a
    per = max(30, -(-n // jobs))
    rdir = Path(ctx["work"]) / "render"
    for f in rdir.glob("part_*.mp4"):
        f.unlink()
    tasks = [(ctx, s, min(b, s + per), str(rdir / f"part_{k:03d}.mp4"), k) for k, s in enumerate(range(a, b, per))]
    log(f"render: {n} cuadros ({n / fps:.1f} s) en {len(tasks)} procesos · {'borrador' if draft else '1080x1920'}")
    # sound cues come from the overlay runtime (cards, pops, typing…) + layout changes
    pg = Pages({"under": ctx["html"]["under"]})
    events = pg.events()
    pg.close()
    for s in ctx["segs"][1:]:
        events.append({"t": s["t0"], "sfx": "whoosh" if s["opt"].get("transition") == "zoom" else "swoosh"})
    sfx_cfg = ctx["plan"].get("sfx", {})
    for e in (sfx_cfg.get("extra", []) if isinstance(sfx_cfg, dict) else []):
        events.append({"t": at(e["at"], ctx["words"], ctx["dur"]), "sfx": e["name"], "dur": e.get("dur", 0)})
    events.sort(key=lambda e: e["t"])
    write_json(rdir / "events.json", events)
    if len(tasks) == 1:
        parts = [_chunk(tasks[0])]
    else:
        with mp.get_context("spawn").Pool(len(tasks)) as pool:
            parts = pool.map(_chunk, tasks)
    lst = rdir / "parts.txt"
    lst.write_text("".join(f"file '{Path(p).name}'\n" for p in parts))
    video = rdir / "video.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", video])
    wav = rdir / "mix.wav"
    audio.build(Path(ctx["work"]), events, (b - a) / fps, ctx["plan"], Path(ctx["base"]), wav, t_from=a / fps)
    outp = Path(ctx["out"])
    if t_from or t_to:
        outp = outp.with_name(outp.stem + f"_{a / fps:.0f}-{b / fps:.0f}s" + outp.suffix)
    outp.parent.mkdir(parents=True, exist_ok=True)
    run(["ffmpeg", "-y", "-v", "error", "-i", video, "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
         "-b:a", "192k", "-ar", "48000", "-shortest", "-movflags", "+faststart", outp])
    for p in parts:
        Path(p).unlink(missing_ok=True)
    log(f"listo: {outp} ({(b - a) / fps:.1f} s de video en {time.time() - t_start:.0f} s)")
    return outp


def stills(ctx, times):
    """Single frames as PNG, for checking a layout or a card without rendering everything."""
    import cv2
    outdir = Path(ctx["work"]) / "stills"
    outdir.mkdir(exist_ok=True)
    paths = []
    for t in times:
        i = min(ctx["frames"] - 1, max(0, int(round(t * ctx["fps"]))))
        fr = Frames(ctx, i)
        img = fr.render(i)
        fr.close()
        p = outdir / f"still_{t:07.2f}s.png"
        cv2.imwrite(str(p), img[..., ::-1])
        paths.append(p)
        log(f"cuadro {t:.2f}s → {p}")
    return paths
