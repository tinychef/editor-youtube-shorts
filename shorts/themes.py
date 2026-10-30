"""Visual themes: CSS variables for the overlays + background and speaker styling for the compositor."""
import copy

import cv2
import numpy as np

FONTS = {
    "--font-ui": "'Inter', system-ui, sans-serif",
    "--font-display": "'Montserrat', 'Inter', sans-serif",
    "--font-mono": "'JetBrains Mono', ui-monospace, monospace",
    "--font-eyebrow": "'Inter', sans-serif",
    "--font-cap": "'Montserrat', 'Inter', sans-serif",
    "--cap-weight": "900", "--cap-size": "78px", "--cap-tracking": "-0.5px", "--cap-case": "none", "--cap-stroke": "15px",
}

THEMES = {
    # cream paper with a faint grid, lime accent — bright, clean, very legible on phones
    "claro": {
        "bg": {"kind": "grid", "color": "#F1EEE6", "line": (20, 20, 10, 0.06), "cell": 44, "vignette": 0.10},
        "speaker": {"outline": "#FFFFFF", "outline_px": 14, "shadow": 0.28, "frame_shadow": 0.22},
        "vars": {
            "--text": "#17181A", "--muted": "#85817A", "--card": "#FFFFFF", "--card-border": "1.5px solid #E5E0D5",
            "--card-shadow": "0 18px 44px rgba(40,32,10,.14), 0 2px 6px rgba(0,0,0,.06)",
            "--dark": "#141517", "--on-dark": "#FFFFFF", "--on-dark-muted": "#9AA0A8", "--dark-border": "1.5px solid #222428",
            "--accent": "#C8F23A", "--on-accent": "#0F1105", "--accent-text": "#4B7A00",
            "--danger": "#E5484D", "--success": "#2A9D63", "--line": "#ECE8DF", "--chrome": "#F4F2EC",
            "--radius": "26px", "--pill-radius": "999px", "--pill-shadow": "0 4px 10px rgba(0,0,0,.12)",
            "--logo-shadow": "0 8px 18px rgba(0,0,0,.15)",
        },
    },
    # charcoal with a soft top light and dots, same lime accent — the «tech at night» look
    "oscuro": {
        "bg": {"kind": "dots", "color": "#121417", "dot": (255, 255, 255, 0.05), "cell": 34, "glow": "#262B33", "vignette": 0.35},
        "speaker": {"outline": "#FFFFFF", "outline_px": 14, "shadow": 0.45, "frame_shadow": 0.45},
        "vars": {
            "--text": "#F3F4F6", "--muted": "#8A9099", "--card": "#1C1F24", "--card-border": "1.5px solid #2B3038",
            "--card-shadow": "0 22px 50px rgba(0,0,0,.5), 0 2px 6px rgba(0,0,0,.3)",
            "--dark": "#0B0C0E", "--on-dark": "#FFFFFF", "--on-dark-muted": "#8A9099", "--dark-border": "1.5px solid #24272d",
            "--accent": "#C8F23A", "--on-accent": "#0E0F10", "--accent-text": "#C8F23A",
            "--danger": "#FF5C5C", "--success": "#3DD68C", "--line": "#2A2E35", "--chrome": "#24282E",
            "--radius": "26px", "--pill-radius": "999px", "--pill-shadow": "0 4px 12px rgba(0,0,0,.35)",
            "--logo-shadow": "0 8px 20px rgba(0,0,0,.4)",
        },
    },
    # tonyciencia brand: amber, hard pixel shadows, square corners, pixel eyebrows
    "tonyciencia": {
        "bg": {"kind": "dots", "color": "#F6F0E4", "dot": (60, 40, 10, 0.10), "cell": 26, "vignette": 0.08},
        "speaker": {"outline": "#FFFFFF", "outline_px": 14, "shadow": 0.0, "hard_shadow": (10, 10, "#2B2118"),
                    "frame_shadow": 0.0},
        "vars": {
            "--text": "#1F1A14", "--muted": "#7B6F5F", "--card": "#FFFDF8", "--card-border": "3px solid #2B2118",
            "--card-shadow": "8px 8px 0 #2B2118",
            "--dark": "#2B2118", "--on-dark": "#FFF8EC", "--on-dark-muted": "#C9B89C", "--dark-border": "3px solid #2B2118",
            "--accent": "#C8922A", "--on-accent": "#1A1208", "--accent-text": "#8A5A12",
            "--danger": "#D2453B", "--success": "#3E8E41", "--line": "#E8DECB", "--chrome": "#F3EADB",
            "--radius": "4px", "--pill-radius": "4px", "--pill-shadow": "4px 4px 0 #2B2118",
            "--logo-shadow": "4px 4px 0 #2B2118", "--font-eyebrow": "'Silkscreen', monospace",
        },
    },
}


def theme(spec):
    """'claro' | 'oscuro' | 'tonyciencia' | {"base": "claro", "accent": "#FF5500", "vars": {...}, ...}."""
    if isinstance(spec, str) or spec is None:
        spec = {"base": spec or "claro"}
    base = spec.get("base", "claro")
    if base not in THEMES:
        raise SystemExit(f"tema desconocido «{base}»: usa {', '.join(THEMES)}")
    th = copy.deepcopy(THEMES[base])
    th["name"] = base
    th["vars"] = {**FONTS, **th["vars"], **spec.get("vars", {})}
    if spec.get("accent"):
        th["vars"]["--accent"] = spec["accent"]
        th["vars"]["--accent-text"] = spec.get("accent_text", spec["accent"] if base == "oscuro" else th["vars"]["--accent-text"])
    if spec.get("on_accent"):
        th["vars"]["--on-accent"] = spec["on_accent"]
    for k in ("bg", "speaker"):
        if isinstance(spec.get(k), dict):
            th[k].update(spec[k])
    return th


def css_vars(th):
    return ":root{" + ";".join(f"{k}:{v}" for k, v in th["vars"].items()) + "}"


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def background(th, W, H):
    """Static background (float32 RGB 0..1)."""
    b = th["bg"]
    col = np.array(hex_rgb(b["color"]), np.float32) / 255
    img = np.ones((H, W, 3), np.float32) * col
    if b.get("glow"):
        g = np.array(hex_rgb(b["glow"]), np.float32) / 255
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt(((xx - W / 2) / (W * 0.9)) ** 2 + ((yy - H * 0.18) / (H * 0.55)) ** 2)
        k = np.clip(1 - r, 0, 1)[..., None] ** 1.6
        img = img * (1 - k) + g * k
    cell = b.get("cell", 40)
    if b["kind"] == "grid":
        r, g_, bb, a = b["line"]
        lc = np.array([r, g_, bb], np.float32) / 255
        m = np.zeros((H, W), np.float32)
        m[(np.arange(H) % cell) < 2, :] = 1
        m[:, (np.arange(W) % cell) < 2] = 1
        m = cv2.GaussianBlur(m, (0, 0), 0.6) * a
        img = img * (1 - m[..., None]) + lc * m[..., None]
    elif b["kind"] == "dots":
        r, g_, bb, a = b["dot"]
        lc = np.array([r, g_, bb], np.float32) / 255
        m = np.zeros((H, W), np.float32)
        for y in range(cell // 2, H, cell):
            for x in range(cell // 2, W, cell):
                cv2.circle(m, (x, y), 2, 1.0, -1, lineType=cv2.LINE_AA)
        m *= a
        img = img * (1 - m[..., None]) + lc * m[..., None]
    v = b.get("vignette", 0)
    if v:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt(((xx - W / 2) / (W * 0.75)) ** 2 + ((yy - H / 2) / (H * 0.75)) ** 2)
        img *= (1 - v * np.clip(r - 0.35, 0, 1) ** 1.5)[..., None]
    return np.clip(img, 0, 1)
