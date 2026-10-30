"""Jump cuts: drop pauses, fillers and retakes; build the cut video + voice track and remap word times."""
import re

import numpy as np

from .util import fmt_t, log, run

FILLER = re.compile(r"^(e+h*|e+m+|m+|mm+h*|a+h+|u+h+|u+m+|ehm+|ah+m+)[.,!?…]*$", re.I)


def keep_ranges(words, duration, fps, max_pause=0.20, pad_in=0.05, pad_out=0.09, fillers=True, drop=()):
    """Source-time [start, end] ranges to keep, snapped to the frame grid."""
    dropped = set()
    for a, b in drop:
        dropped.update(range(int(a), int(b) + 1))
    kept = [i for i, w in enumerate(words)
            if i not in dropped and not (fillers and FILLER.match(w["w"]))]
    if not kept:
        raise SystemExit("No quedó ninguna palabra después de los cortes: revisa --drop.")
    segs = []
    prev = None
    for i in kept:
        w = words[i]
        if prev is None:
            segs.append([max(0.0, w["s"] - pad_in), w["e"] + pad_out, [i]])
        else:
            pw = words[prev]
            gap = w["s"] - pw["e"]
            if i == prev + 1 and gap <= max_pause:
                segs[-1][1] = w["e"] + pad_out
                segs[-1][2].append(i)
            else:
                segs[-1][1] = min(segs[-1][1], pw["e"] + pad_out)
                segs.append([max(w["s"] - pad_in, pw["e"] + 0.01), w["e"] + pad_out, [i]])
        prev = i
    q = lambda t: round(t * fps) / fps
    out = []
    for s, e, idx in segs:
        s, e = q(max(0.0, s)), q(min(duration, e))
        if out and s <= out[-1][1] + 1e-6:
            out[-1][1] = max(out[-1][1], e)
            out[-1][2] += idx
        elif e - s >= 2 / fps:
            out.append([s, e, idx])
    return out


def remap(words, ranges):
    """Words in output time (only the kept ones, re-indexed)."""
    res, t = [], 0.0
    for s, e, idx in ranges:
        for i in idx:
            w = words[i]
            res.append({"w": w["w"], "s": round(t + max(0.0, w["s"] - s), 3),
                        "e": round(t + min(e - s, w["e"] - s), 3), "p": w.get("p", 1.0), "src": i})
        t += e - s
    for k, w in enumerate(res):
        w["i"] = k
    return res, t


def hdr_filter(src):
    """iPhone/Android HDR (HLG/PQ) → SDR BT.709, otherwise colors look washed out."""
    p = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=color_transfer",
             "-of", "default=nw=1:nk=1", src])
    trc = p.stdout.strip()
    if trc in ("arib-std-b67", "smpte2084"):
        log(f"video HDR ({trc}): convirtiendo a SDR")
        return ("zscale=t=linear:npl=203,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable:desat=0,"
                "zscale=t=bt709:m=bt709:r=tv,format=yuv420p,")
    return ""


def cut_video(src, ranges, out, fps, max_side=1920):
    """Frame-accurate select of the kept ranges at a constant frame rate (no trim/concat buffering)."""
    expr = "+".join(f"between(t,{s:.4f},{e - 0.5 / fps:.4f})" for s, e, _ in ranges)
    vf = (f"{hdr_filter(src)}fps={fps:g},select='{expr}',setpts=N/{fps:g}/TB,"
          f"scale='if(gt(iw,ih),min(iw,{max_side}),-2)':'if(gt(iw,ih),-2,min(ih,{max_side}))':flags=lanczos"
          f":out_color_matrix=bt709:out_range=tv")
    run(["ffmpeg", "-y", "-v", "error", "-i", src, "-vf", vf, "-an", "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "12", "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709",
         "-color_trc", "bt709", "-r", f"{fps:g}", out])


def cut_audio(src, ranges, out, sr=48000, xfade=0.006):
    """Sample-accurate audio cut with tiny equal-power crossfades at every join (no clicks)."""
    import soundfile as sf
    p = run(["ffmpeg", "-v", "error", "-i", src, "-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"], text=False)
    a = np.frombuffer(p.stdout, np.float32)
    n = int(xfade * sr)
    ramp = np.sin(np.linspace(0, np.pi / 2, n, dtype=np.float32)) ** 2
    parts = []
    for s, e, _ in ranges:
        seg = a[int(round(s * sr)):int(round(e * sr))].copy()
        if len(seg) > 2 * n:
            seg[:n] *= ramp
            seg[-n:] *= ramp[::-1]
        parts.append(seg)
    y = np.concatenate(parts) if parts else np.zeros(1, np.float32)
    sf.write(out, y, sr, subtype="FLOAT")
    return len(y) / sr


def transcript_text(words, per_line=10):
    """Readable transcript with word indices, for Claude to plan the edit."""
    lines, cur = [], []
    for w in words:
        cur.append(f"({w['i']}){w['w']}")
        end = w["w"][-1:] in ".?!…"
        if len(cur) >= per_line or end:
            lines.append(f"[{fmt_t(words[int(cur[0][1:cur[0].index(')')])]['s'])}] " + " ".join(cur))
            cur = []
    if cur:
        lines.append(f"[{fmt_t(words[int(cur[0][1:cur[0].index(')')])]['s'])}] " + " ".join(cur))
    return "\n".join(lines) + "\n"


def summary(words_src, ranges, duration):
    kept = sum(e - s for s, e, _ in ranges)
    log(f"cortes: {len(ranges)} tomas · {duration:.1f}s → {kept:.1f}s ({100 * (1 - kept / max(duration, 1e-6)):.0f}% fuera)")
