"""`python -m shorts doctor`: checks every dependency and says exactly how to fix what's missing."""
import importlib
import shutil
import subprocess
import sys

OK, BAD = "✓", "✗"


def doctor():
    problems = 0

    def line(ok, what, fix=""):
        nonlocal problems
        print(f"  {OK if ok else BAD} {what}" + ("" if ok else f"\n      → {fix}"))
        problems += 0 if ok else 1

    print("Editor de Shorts · revisión del entorno")
    v = sys.version_info
    line(v >= (3, 10), f"Python {v.major}.{v.minor}", "Instala Python 3.10 o más nuevo (python.org)")
    for tool in ("ffmpeg", "ffprobe"):
        line(shutil.which(tool) is not None, tool,
             "Instala ffmpeg: Mac `brew install ffmpeg` · Windows `winget install Gyan.FFmpeg` · Linux `sudo apt install ffmpeg`")
    if shutil.which("ffmpeg"):
        f = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
        line(" zscale " in f, "ffmpeg con zscale (videos HDR de iPhone)",
             "Opcional: usa un ffmpeg completo (brew/winget/gyan.dev) si grabas en HDR")
    for mod, pip in (("numpy", "numpy"), ("scipy", "scipy"), ("cv2", "opencv-python-headless"), ("PIL", "pillow"),
                     ("soundfile", "soundfile"), ("faster_whisper", "faster-whisper"), ("playwright", "playwright")):
        try:
            importlib.import_module(mod)
            line(True, f"módulo {pip}")
        except Exception as e:
            line(False, f"módulo {pip} ({e.__class__.__name__})", "pip install -e .   (desde la carpeta del repo)")
    try:
        importlib.import_module("mediapipe")
        from mediapipe.tasks.python import vision  # noqa: F401
        line(True, "módulo mediapipe")
    except OSError as e:
        line(False, f"mediapipe no carga ({e})", "Linux: sudo apt install libegl1 libgles2")
    except Exception as e:
        line(False, f"mediapipe ({e.__class__.__name__})", "pip install -e .")
    try:
        from playwright.sync_api import sync_playwright
        from .overlay import chromium_args
        with sync_playwright() as p:
            b = p.chromium.launch(**chromium_args())
            b.close()
        line(True, "Chromium para las tarjetas (Playwright)")
    except Exception as e:
        line(False, f"Chromium no arranca ({str(e).splitlines()[0][:120]})", "python -m playwright install chromium")
    print("\nTodo listo." if not problems else f"\n{problems} cosa(s) por arreglar.")
    return 1 if problems else 0
