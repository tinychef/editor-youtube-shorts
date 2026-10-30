"""Shared helpers: subprocess, ffprobe, paths, time references and easing."""
import json
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
CACHE = Path(os.environ.get("SHORTS_CACHE", Path.home() / ".cache" / "editor-shorts"))

W, H = 1080, 1920  # output canvas (9:16)


def log(*a):
    print("·", *a, file=sys.stderr, flush=True)


def run(cmd, **kw):
    """Run a command; on failure show its stderr tail instead of a bare traceback."""
    p = subprocess.run([str(c) for c in cmd], capture_output=True, text=kw.pop("text", True), **kw)
    if p.returncode != 0:
        err = p.stderr if isinstance(p.stderr, str) else p.stderr.decode("utf8", "replace")
        raise RuntimeError(f"{Path(str(cmd[0])).name} falló ({p.returncode}):\n{err[-2500:]}")
    return p


def need(tool):
    if not shutil.which(tool):
        raise SystemExit(f"Falta «{tool}» en el PATH. Instálalo (ver README → Instalación).")
    return tool


def probe(path):
    """Size, fps, duration, rotation and audio presence of a video."""
    need("ffprobe")
    p = run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", path])
    d = json.loads(p.stdout)
    v = next((s for s in d["streams"] if s["codec_type"] == "video"), None)
    if v is None:
        raise SystemExit(f"{path} no tiene pista de video.")
    a = next((s for s in d["streams"] if s["codec_type"] == "audio"), None)
    num, den = (v.get("avg_frame_rate") or v.get("r_frame_rate") or "30/1").split("/")
    fps = float(num) / float(den or 1) if float(num) else 30.0
    rot = 0
    for sd in v.get("side_data_list", []) or []:
        if "rotation" in sd:
            rot = int(float(sd["rotation"]))
    rot = int(v.get("tags", {}).get("rotate", rot))
    w, h = int(v["width"]), int(v["height"])
    if abs(rot) % 180 == 90:
        w, h = h, w
    dur = float(d["format"].get("duration") or v.get("duration") or 0)
    return {"width": w, "height": h, "fps": fps, "duration": dur, "audio": a is not None,
            "sample_rate": int(a["sample_rate"]) if a else None}


def read_json(p, default=None):
    p = Path(p)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf8"))


def write_json(p, data):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf8")


# ── time references used by plans ──────────────────────────────────────────
# number        → seconds of the edited (output) video
# "w:12"        → start of word 12        "w:12.e" → end of word 12
# "+1.5"        → relative to the item's own start (only for until/dur)
# "end"         → end of the video        "12.5" (string) → seconds
_WREF = re.compile(r"^w:(\d+)(\.e)?([+-]\d+(?:\.\d+)?)?$")


def at(ref, words, duration, base=None):
    if ref is None:
        return None
    if isinstance(ref, (int, float)):
        return float(ref)
    s = str(ref).strip()
    if s == "end":
        return float(duration)
    if s.startswith("+") and base is not None:
        return base + float(s[1:])
    m = _WREF.match(s)
    if m:
        i = int(m.group(1))
        if not 0 <= i < len(words):
            raise ValueError(f"referencia {s}: solo hay {len(words)} palabras (0–{len(words) - 1})")
        t = words[i]["e"] if m.group(2) else words[i]["s"]
        return t + float(m.group(3) or 0)
    try:
        return float(s)
    except ValueError:
        raise ValueError(f"referencia de tiempo no válida: {ref!r} (usa segundos, 'w:N', 'w:N.e', '+s' o 'end')")


def span(item, words, duration, default_dur=2.5):
    """Resolve an item's [t0, t1] from at/until/dur."""
    t0 = at(item.get("at", 0), words, duration)
    if "until" in item:
        t1 = at(item["until"], words, duration, base=t0)
    elif "dur" in item:
        t1 = t0 + float(item["dur"])
    else:
        t1 = t0 + default_dur
    return max(0.0, t0), min(float(duration), max(t0 + 0.05, t1))


# ── easing ──────────────────────────────────────────────────────────────────
def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def smooth(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_in_out(x):
    x = clamp(x)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def back_out(x, s=1.6):
    x = clamp(x) - 1
    return 1 + (s + 1) * x ** 3 + s * x ** 2


def lerp(a, b, k):
    return a + (b - a) * k


def fmt_t(t):
    m, s = divmod(max(0.0, t), 60)
    return f"{int(m):02d}:{s:05.2f}"


def slug(s):
    s = s.lower().strip()
    s = re.sub(r"[áàä]", "a", s); s = re.sub(r"[éèë]", "e", s); s = re.sub(r"[íìï]", "i", s)
    s = re.sub(r"[óòö]", "o", s); s = re.sub(r"[úùü]", "u", s); s = s.replace("ñ", "n")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") or "video"


def isclose(a, b, tol=1e-6):
    return math.isclose(a, b, abs_tol=tol)
