"""Brand logos for cards: your own files first, then Simple Icons (CC0), app-icon monograms, then favicons.

A logo spec in a plan can be:
  "claude"                      name, alias or Simple Icons slug
  "photoshop"                   built-in app-icon monogram (Adobe/Microsoft apps aren't in Simple Icons)
  "meetily.ai"                  a domain → the site's icon (via Google's favicon service)
  "logos/mi-marca.png"          a file (relative to the plan) — always wins
  {"text": "Ps", "bg": "#001E36", "fg": "#31A8FF"}   a monogram you design
  {"name": "Twenty", "domain": "twenty.com"}         name with a domain fallback
Put your own logos in a `logos/` folder next to the plan (logos/<nombre>.png|svg) to override anything.
"""
import base64
import hashlib
import json
import re
import unicodedata
import urllib.request
from pathlib import Path

from .util import CACHE, log

SI_VER = "16.36.0"
SI_URL = f"https://cdn.jsdelivr.net/npm/simple-icons@{SI_VER}"
UA = {"User-Agent": "Mozilla/5.0 (editor-youtube-shorts)"}

ALIAS = {
    "chatgpt": "chatgpt.com", "openai": "openai.com", "gpt": "chatgpt.com", "sora": "openai.com",
    "claude code": "claude", "claudecode": "claude", "gemini": "googlegemini", "google gemini": "googlegemini",
    "google fotos": "googlephotos", "google photos": "googlephotos", "fotos": "googlephotos",
    "google maps": "googlemaps", "maps": "googlemaps", "drive": "googledrive", "google drive": "googledrive",
    "sheets": "googlesheets", "google sheets": "googlesheets", "meet": "googlemeet", "google meet": "googlemeet",
    "twitter": "x", "vs code": "visualstudiocode", "vscode": "visualstudiocode", "davinci": "davinciresolve",
    "hugging face": "huggingface", "mistral": "mistralai", "meta ai": "metaai", "n8n.io": "n8n",
    "canva": "canva.com", "slack": "slack", "salesforce": "salesforce", "midjourney": "midjourney.com",
    "grok": "grok.com", "xai": "grok.com", "capcut": "capcut", "linkedin": "linkedin", "copilot": "copilot.microsoft.com",
    "lovable": "lovable.dev", "bolt": "bolt.new", "higgsfield": "higgsfield.ai", "kling": "klingai.com",
    "runway": "runwayml.com", "heygen": "heygen.com", "manus": "manus.im", "otter": "otter.ai",
}

# App icons that are letters on a tile (Adobe, Microsoft…) or whose marks were withdrawn from Simple Icons.
PRESETS = {
    "photoshop": ("Ps", "#001E36", "#31A8FF"), "adobephotoshop": ("Ps", "#001E36", "#31A8FF"),
    "illustrator": ("Ai", "#330000", "#FF9A00"), "premiere": ("Pr", "#00005B", "#9999FF"),
    "premiere pro": ("Pr", "#00005B", "#9999FF"), "after effects": ("Ae", "#00005B", "#9999FF"),
    "lightroom": ("Lr", "#001E36", "#31A8FF"), "indesign": ("Id", "#49021F", "#FF3366"),
    "acrobat": ("A", "#EC1C24", "#FFFFFF"), "adobe acrobat": ("A", "#EC1C24", "#FFFFFF"),
    "audition": ("Au", "#00005B", "#9999FF"), "firefly": ("Ff", "#470000", "#FF4E4E"),
    "excel": ("X", "#107C41", "#FFFFFF"), "word": ("W", "#185ABD", "#FFFFFF"), "powerpoint": ("P", "#C43E1C", "#FFFFFF"),
    "outlook": ("O", "#0F6CBD", "#FFFFFF"), "teams": ("T", "#4B53BC", "#FFFFFF"), "onenote": ("N", "#7719AA", "#FFFFFF"),
    "linkedin": ("in", "#0A66C2", "#FFFFFF"), "slack": ("#", "#4A154B", "#FFFFFF"), "salesforce": ("sf", "#00A1E0", "#FFFFFF"),
    "capcut": ("CC", "#000000", "#FFFFFF"),
}


def _get(url, timeout=20):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def _slug(t):
    t = t.lower().replace("+", "plus").replace(".", "dot").replace("&", "and")
    t = unicodedata.normalize("NFD", t)
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in t if not unicodedata.combining(c)))


_SI = None


def _si_index():
    global _SI
    if _SI is None:
        p = CACHE / "logos" / f"si-{SI_VER}.json"
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(_get(f"{SI_URL}/data/simple-icons.json"))
        d = json.loads(p.read_text())
        d = d["icons"] if isinstance(d, dict) else d
        _SI = {}
        for x in d:
            sl = x.get("slug") or _slug(x["title"])
            _SI.setdefault(sl, x | {"slug": sl})
            _SI.setdefault(_slug(x["title"]), x | {"slug": sl})
            for a in (x.get("aliases") or {}).get("aka", []):
                _SI.setdefault(_slug(a), x | {"slug": sl})
    return _SI


def _lum(hexc):
    h = hexc.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _svg(slug, x, style):
    p = CACHE / "logos" / "si" / f"{slug}.svg"
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(_get(f"{SI_URL}/icons/{slug}.svg"))
    path = re.search(r' d="([^"]+)"', p.read_text()).group(1)
    hexc = "#" + x["hex"]
    if style == "light":
        return {"kind": "svg", "path": path, "bg": "#FFFFFF", "fg": hexc if _lum(hexc) < 0.85 else "#111", "title": x["title"]}
    return {"kind": "svg", "path": path, "bg": hexc, "fg": "#111111" if _lum(hexc) > 0.72 else "#FFFFFF", "title": x["title"]}


def _favicon(domain, min_px=120):
    p = CACHE / "logos" / "fav" / f"{domain}.png"
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        try:
            p.write_bytes(_get(f"https://www.google.com/s2/favicons?domain={domain}&sz=256"))
        except Exception as e:
            log(f"logo: no pude bajar el ícono de {domain} ({e})")
            return None
    try:
        from PIL import Image
        im = Image.open(p)
        if min(im.size) < min_px:
            return None
    except Exception:
        return None
    return {"kind": "img", "src": "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode(), "bg": "#FFFFFF",
            "fill": True}


def _file(path):
    path = Path(path)
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
            ".svg": "image/svg+xml"}.get(path.suffix.lower())
    if not mime or not path.exists():
        return None
    return {"kind": "img", "src": f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode(), "bg": "#FFFFFF",
            "fill": False}


def _mono(text, bg=None, fg=None):
    if not bg:
        hue = int(hashlib.md5(text.encode()).hexdigest()[:2], 16) * 360 // 256
        bg = f"hsl({hue},55%,42%)"
    return {"kind": "mono", "text": text, "bg": bg, "fg": fg or "#FFFFFF"}


def resolve(spec, base_dir=None, style="tile"):
    """Logo spec → dict the overlay runtime draws ({kind: svg|img|mono, …}); never raises."""
    if not spec:
        return None
    if isinstance(spec, dict):
        if spec.get("file"):
            got = _file(Path(base_dir or ".") / spec["file"])
            if got:
                return got
        if spec.get("text"):
            return _mono(spec["text"], spec.get("bg"), spec.get("fg"))
        for k in ("slug", "name"):
            if spec.get(k):
                got = resolve(spec[k], base_dir, spec.get("style", style))
                if got and got["kind"] != "mono":
                    return got
        if spec.get("domain"):
            got = _favicon(spec["domain"], 64)
            if got:
                return got
        return _mono((spec.get("name") or "?")[:2])
    s = str(spec).strip()
    key = s.lower()
    for d in filter(None, [Path(base_dir) / "logos" if base_dir else None, Path("logos")]):
        for ext in (".svg", ".png", ".webp", ".jpg", ".jpeg"):
            for nm in (key, _slug(key)):
                if (d / f"{nm}{ext}").exists():
                    return _file(d / f"{nm}{ext}")
    if "/" in s or re.search(r"\.(png|jpe?g|webp|svg)$", key):
        got = _file(Path(base_dir or ".") / s)
        if got:
            return got
    if key in PRESETS:
        return _mono(*PRESETS[key])
    key = ALIAS.get(key, key)
    if key in PRESETS:
        return _mono(*PRESETS[key])
    if re.match(r"^[a-z0-9-]+(\.[a-z0-9-]+)+$", key):
        got = _favicon(key)
        if got:
            return got
    try:
        x = _si_index().get(_slug(key))
        if x:
            return _svg(x["slug"], x, style)
    except Exception as e:
        log(f"logo: Simple Icons no disponible ({e})")
    words = re.findall(r"[A-Za-z0-9]+", s)
    return _mono(("".join(w[0] for w in words[:2]) if len(words) > 1 else s[:2]).capitalize())


def preview(names, out="logos_preview.png"):
    """Render the resolved logos to a PNG to eyeball them."""
    from .overlay import render_html_png
    tiles = []
    for n in names:
        L = resolve(n)
        tiles.append((n, L))
        log(f"{n}: {L['kind'] if L else 'nada'}{' · ' + L.get('title', '') if L and L.get('title') else ''}")
    render_html_png(tiles, out)
    log(f"vista previa: {out}")
