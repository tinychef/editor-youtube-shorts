"""QA: contact sheet of a rendered short + loudness, so Claude (or you) can review it without scrubbing."""
import re
import subprocess
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .util import ASSETS, log, probe, run


def _font(size):
    for f in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/System/Library/Fonts/Helvetica.ttc",
              "C:/Windows/Fonts/arialbd.ttf"):
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def frame_at(video, t, w=270):
    p = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1", "-vf", f"scale={w}:-2",
                        "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True)
    return Image.open(BytesIO(p.stdout)).convert("RGB")


def sheet(video, times, out, cols=6, w=270):
    ims = [frame_at(video, t, w) for t in times]
    h = ims[0].height
    rows = (len(ims) + cols - 1) // cols
    S = Image.new("RGB", (cols * w, rows * h), (16, 16, 16))
    d = ImageDraw.Draw(S)
    f = _font(20)
    for i, (im, t) in enumerate(zip(ims, times)):
        x, y = (i % cols) * w, (i // cols) * h
        S.paste(im, (x, y))
        d.rectangle([x, y, x + 74, y + 28], fill=(0, 0, 0))
        d.text((x + 5, y + 3), f"{t:.1f}s", font=f, fill=(255, 230, 0))
        # YouTube Shorts UI zones (title/buttons) — keep captions and key text out of them
        d.rectangle([x, y + int(h * 0.80), x + w - 1, y + h - 1], outline=(255, 60, 60))
        d.rectangle([x + int(w * 0.86), y + int(h * 0.45), x + w - 1, y + int(h * 0.80)], outline=(255, 60, 60))
    S.save(out, quality=88)
    return out


def qa(video, every=2.0):
    video = Path(video)
    info = probe(video)
    d = info["duration"]
    n = max(1, int(d / every))
    times = [min(d - 0.05, 0.3 + i * every) for i in range(n)]
    out = video.with_name(video.stem + "_qa.jpg")
    sheet(video, times, out)
    p = run(["ffmpeg", "-v", "info", "-i", str(video), "-af", "ebur128=peak=true", "-f", "null", "-"])
    I = re.findall(r"I:\s+(-?[\d.]+) LUFS", p.stderr)
    TP = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", p.stderr)
    log(f"{video.name}: {info['width']}x{info['height']} · {info['fps']:.0f} fps · {d:.1f} s · "
        f"loudness {I[-1] if I else '?'} LUFS · pico {TP[-1] if TP else '?'} dBTP")
    log(f"hoja de contactos: {out} (recuadros rojos = zona de botones/título de YouTube)")
    return out
