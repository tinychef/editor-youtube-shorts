"""Visual themes: CSS variables for the overlays + background and speaker styling for the compositor."""
import copy
import math

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
# variables the motion-graphics components use; every theme gets these unless it sets its own
COMMON = {
    "--grad": "linear-gradient(90deg, var(--accent), var(--accent))",
    "--fill": "rgba(120,120,128,.16)", "--switch-on": "var(--success)",
    "--bubble-me": "var(--accent)", "--on-bubble-me": "var(--on-accent)", "--bubble-them": "var(--chrome)",
    "--island": "#000000",
}
# Apple's system stack: SF Pro on a Mac (Text for UI, Display for big type), Inter elsewhere (bundled, OFL)
SF_TEXT = "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'SF Pro Display', 'Inter Var', 'Inter', system-ui, sans-serif"
SF_DISPLAY = "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Inter Var', 'Inter', system-ui, sans-serif"
IG_GRADIENT = "linear-gradient(90deg, #FF7A00 0%, #FF0069 36%, #D300C5 70%, #7638FA 100%)"

THEMES = {
    # iOS grouped-background grey with a dot grid that scrolls up (parallax), white iOS cards, Instagram pink
    "ios": {
        "bg": {"kind": "dots", "color": "#F2F2F7", "cell": 28, "dot": 2.2, "dot_color": "#C7C7CC", "scroll": 40,
               "parallax": {"speed": 0.5, "cell": 56, "dot": 4.6, "alpha": 0.42}},
        "speaker": {"outline": "#FFFFFF", "outline_px": 14, "shadow": 0.28, "frame_shadow": 0.22},
        "vars": {
            "--font-ui": SF_TEXT, "--font-display": SF_DISPLAY, "--font-eyebrow": SF_TEXT, "--font-cap": SF_DISPLAY,
            "--font-mono": "ui-monospace, 'SF Mono', 'JetBrains Mono', monospace",
            "--cap-weight": "800", "--cap-tracking": "-0.02em", "--track-ui": "-0.01em", "--track-display": "-0.025em",
            "--text": "#000000", "--muted": "#8E8E93", "--card": "#FFFFFF", "--card-border": "1.5px solid rgba(60,60,67,.12)",
            "--card-shadow": "0 8px 24px rgba(0,0,0,.08)",
            "--dark": "#1C1C1E", "--on-dark": "#FFFFFF", "--on-dark-muted": "#98989D", "--dark-border": "1.5px solid #2C2C2E",
            "--accent": "#FF0069", "--on-accent": "#FFFFFF", "--accent-text": "#D6005C",
            "--danger": "#FF3B30", "--success": "#34C759", "--line": "#C6C6C8", "--chrome": "#F2F2F7",
            "--radius": "26px", "--pill-radius": "999px", "--pill-shadow": "0 4px 12px rgba(0,0,0,.10)",
            "--logo-shadow": "0 6px 16px rgba(0,0,0,.12)",
            "--grad": IG_GRADIENT, "--fill": "#E9E9EB", "--bubble-them": "#E9E9EB",
            "--cta-bg": "var(--grad)", "--badge-bg": "var(--grad)", "--badge-fg": "#FFFFFF",
            "--check-bg": "var(--success)", "--check-fg": "#FFFFFF",
        },
    },
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


DEFAULT = "ios"


def theme(spec):
    """'ios' | 'claro' | 'oscuro' | 'tonyciencia' | {"base": "ios", "accent": "#FF5500", "vars": {...}, "bg": {...}}."""
    if isinstance(spec, str) or spec is None:
        spec = {"base": spec or DEFAULT}
    base = spec.get("base", DEFAULT)
    if base not in THEMES:
        raise SystemExit(f"tema desconocido «{base}»: usa {', '.join(THEMES)}")
    th = copy.deepcopy(THEMES[base])
    th["name"] = base
    th["vars"] = {**FONTS, **COMMON, **th["vars"], **spec.get("vars", {})}
    if spec.get("accent"):
        th["vars"]["--accent"] = spec["accent"]
        auto = spec["accent"] if base == "oscuro" else darken(spec["accent"]) if base == "ios" else th["vars"]["--accent-text"]
        th["vars"]["--accent-text"] = spec.get("accent_text", auto)
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


def darken(h, k=0.16):
    return "#" + "".join(f"{round(c * (1 - k)):02X}" for c in hex_rgb(h))


def background(th, W, H, dots=True):
    """Static background (float32 RGB 0..1). dots=False leaves out the dot grid (Backdrop draws it per frame)."""
    b = th["bg"]
    if dots and b["kind"] == "dots" and "scroll" in b:
        return Backdrop(th, W, H).frame(0.0) / 255
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
    elif b["kind"] == "dots" and dots:
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


class Backdrop:
    """The compositor's background, one call per frame.

    Themes with ``bg.scroll`` (px/s, negative = downwards) get a dot grid that moves vertically, plus an optional
    second layer of bigger, fainter dots at a fraction of the speed (``bg.parallax``). The grid repeats every
    ``cell`` px, so the motion loops with no jumps, and each frame is drawn analytically (anti-aliased at any
    sub-pixel offset) on one small periodic tile that is then repeated over the canvas. Everything else in the
    background (color, glow, vignette) is static and computed once. Themes without ``scroll`` return the same
    image every frame.
    """

    def __init__(self, th, W, H, k=1.0):
        self.W, self.H = W, H
        b = th["bg"]
        self.layers = []
        if b["kind"] == "dots" and "scroll" in b:
            self.layers = self._layers(b, k)
        self.static = (background(th, W, H, dots=not self.layers) * 255).astype(np.float32)
        self.flat = not b.get("glow") and not b.get("vignette")
        self.base = np.array(hex_rgb(b["color"]), np.float32)
        if self.layers:
            self.by = math.lcm(*[L["cell"] for L in self.layers])
            self.bx = self.by
            self.x0 = (W % self.layers[0]["cell"]) / 2           # centre the grid horizontally

    @staticmethod
    def _layers(b, k):
        cell = max(4, round(float(b.get("cell", 28)) * k))
        dot = b.get("dot", 2.2)
        r = float(dot if isinstance(dot, (int, float)) else b.get("dot_r", 2.0)) * k
        col = b.get("dot_color") or (dot[:3] if not isinstance(dot, (int, float)) else "#C7C7CC")
        alpha = float(b.get("dot_alpha", 1.0 if isinstance(dot, (int, float)) else dot[3]))
        speed = float(b.get("scroll", 0)) * k
        layers = []
        par = b.get("parallax")
        if par:
            par = {"speed": float(par)} if isinstance(par, (int, float)) else dict(par)
            pc = max(1, round(float(par.get("cell", 2 * b.get("cell", 28))) * k / cell)) * cell   # a multiple of cell
            layers.append({"cell": pc, "r": float(par.get("dot", 2 * float(r / k))) * k,
                           "color": par.get("color", col), "alpha": float(par.get("alpha", 0.42)),
                           "speed": speed * float(par.get("speed", 0.5)), "dx": (cell - pc / 2) % cell})   # between columns
        layers.append({"cell": cell, "r": r, "color": col, "alpha": alpha, "speed": speed, "dx": 0.0})
        for L in layers:
            c = L["color"]
            L["rgb"] = np.array(hex_rgb(c) if isinstance(c, str) else c[:3], np.float32)
        return layers

    def _cover(self, L, t):
        """Coverage (0..1) of one dot layer on the by×bx tile at time t: distance to the nearest dot centre."""
        c = L["cell"]
        cy = (c / 2 - L["speed"] * t) % c
        cx = (c / 2 + self.x0 + L["dx"]) % c
        yy = (np.arange(self.by, dtype=np.float32) + 0.5 - cy) % c
        xx = (np.arange(self.bx, dtype=np.float32) + 0.5 - cx) % c
        yy = np.minimum(yy, c - yy)[:, None]
        xx = np.minimum(xx, c - xx)[None, :]
        d = np.sqrt(yy * yy + xx * xx)
        return np.clip(L["r"] + 0.5 - d, 0, 1) * L["alpha"]

    def frame(self, t):
        """float32 HxWx3 (0..255), a fresh array the caller may draw on."""
        if not self.layers:
            return self.static.copy()
        if self.flat:
            tile = np.empty((self.by, self.bx, 3), np.float32)
            tile[:] = self.base
            for L in self.layers:
                m = self._cover(L, t)[..., None]
                tile += m * (L["rgb"] - tile)
            reps = (-(-self.H // self.by), -(-self.W // self.bx), 1)
            return np.ascontiguousarray(np.tile(tile, reps)[: self.H, : self.W])
        # glow/vignette: dots over the static image, shaded by it (same look as the static dots)
        img = self.static.copy()
        shade = img / np.maximum(self.base, 1)
        for L in self.layers:
            m = np.tile(self._cover(L, t), (-(-self.H // self.by), -(-self.W // self.bx)))[: self.H, : self.W, None]
            img += m * (L["rgb"] * shade - img)
        return img
