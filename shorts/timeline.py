"""Plan overlays → items the overlay runtime animates (resolved times, zones, logos, defaults)."""
import re
from pathlib import Path

from . import logos as L
from .util import at, span

# layer: under = behind the speaker cut-out, over = in front of it
# place: stack (cards stack in the graphics zone) · header · title · abs · full · cap
T = {
    "hook":      dict(layer="over", place="title", inn=("none", 0.0), out=("fade", 0.2), sfx="rise", dur=2.6),
    "title":     dict(layer="over", place="title", inn=("pop", 0.3), out=("fade", 0.2), sfx="pop", dur=2.0),
    "section":   dict(layer="under", place="header", inn=("down", 0.3), out=("fade", 0.2), sfx="swoosh", dur=4.0),
    "app":       dict(layer="under", place="stack", inn=("up", 0.35), out=("fade", 0.22), sfx="whoosh", dur=3.0),
    "logos":     dict(layer="under", place="stack", inn=("none", 0.0), out=("fade", 0.22), sfx=None, dur=3.0),
    "logo":      dict(layer="under", place="stack", inn=("pop", 0.35), out=("fade", 0.2), sfx="pop", dur=2.0),
    "list":      dict(layer="under", place="stack", inn=("up", 0.35), out=("fade", 0.22), sfx="whoosh", dur=4.0),
    "repo":      dict(layer="under", place="stack", inn=("up", 0.35), out=("fade", 0.22), sfx="whoosh", dur=3.0),
    "browser":   dict(layer="under", place="stack", inn=("up", 0.4), out=("fade", 0.22), sfx="whoosh", dur=4.0),
    "terminal":  dict(layer="under", place="stack", inn=("up", 0.35), out=("fade", 0.22), sfx="whoosh", dur=4.0),
    "search":    dict(layer="under", place="stack", inn=("up", 0.35), out=("fade", 0.22), sfx="whoosh", dur=3.0),
    "checklist": dict(layer="under", place="stack", inn=("up", 0.35), out=("fade", 0.22), sfx="whoosh", dur=3.5),
    "stat":      dict(layer="under", place="stack", inn=("up", 0.35), out=("fade", 0.22), sfx="whoosh", dur=3.0),
    "compare":   dict(layer="under", place="stack", inn=("up", 0.35), out=("fade", 0.22), sfx="whoosh", dur=3.0),
    "chat":      dict(layer="under", place="stack", inn=("up", 0.35), out=("fade", 0.22), sfx="whoosh", dur=4.0),
    "image":     dict(layer="under", place="stack", inn=("up", 0.35), out=("fade", 0.22), sfx="whoosh", dur=3.0),
    "html":      dict(layer="under", place="stack", inn=("up", 0.35), out=("fade", 0.22), sfx="whoosh", dur=3.0),
    "badge":     dict(layer="over", place="abs", inn=("pop", 0.3), out=("fade", 0.15), sfx="pop", dur=1.6),
    "stamp":     dict(layer="over", place="abs", inn=("stamp", 0.2), out=("fade", 0.2), sfx="thump", dur=1.5),
    "cta":       dict(layer="over", place="title", inn=("up", 0.45), out=("fade", 0.3), sfx="whoosh", dur=None),
    "cursor":    dict(layer="over", place="abs", inn=("fade", 0.15), out=("fade", 0.15), sfx=None, dur=1.2),
    "arrow":     dict(layer="over", place="full", inn=("none", 0.0), out=("fade", 0.2), sfx="swoosh", dur=1.8),
    "scrim":     dict(layer="over", place="full", inn=("fade", 0.3), out=("fade", 0.3), sfx=None, dur=2.6),
    # motion graphics (iOS / Instagram); their sounds come from their animated parts
    "notif":      dict(layer="over", place="top", inn=("drop", 0.5), out=("drop", 0.35), sfx="notif", dur=2.6),
    "island":     dict(layer="over", place="top", inn=("fade", 0.12), out=("fade", 0.12), sfx=None, dur=2.6),
    "imessage":   dict(layer="under", place="stack", inn=("up", 0.35), out=("fade", 0.22), sfx="whoosh", dur=4.5),
    "toggle":     dict(layer="under", place="stack", inn=("up", 0.35), out=("fade", 0.22), sfx="whoosh", dur=2.6),
    "rings":      dict(layer="under", place="stack", inn=("up", 0.35), out=("fade", 0.22), sfx="whoosh", dur=3.0),
    "chart":      dict(layer="under", place="stack", inn=("up", 0.35), out=("fade", 0.22), sfx="whoosh", dur=3.5),
    "odometer":   dict(layer="under", place="stack", inn=("pop", 0.3), out=("fade", 0.2), sfx="softpop", dur=3.0),
    "homescreen": dict(layer="under", place="stack", inn=("none", 0.0), out=("fade", 0.22), sfx=None, dur=3.0),
    "iphone":     dict(layer="under", place="stack", inn=("up", 0.45), out=("fade", 0.25), sfx="whoosh", dur=4.0),
    "marker":     dict(layer="over", place="title", inn=("pop", 0.3), out=("fade", 0.2), sfx="softpop", dur=2.0),
    "hearts":     dict(layer="over", place="full", inn=("none", 0.0), out=("none", 0.0), sfx=None, dur=2.6),
    "confetti":   dict(layer="under", place="abs", inn=("none", 0.0), out=("none", 0.0), sfx=None, dur=1.8),
    "sparkle":    dict(layer="under", place="abs", inn=("none", 0.0), out=("none", 0.0), sfx=None, dur=1.4),
    "punch":      dict(layer="over", place="full", inn=("fade", 0.05), out=("fade", 0.1), sfx="thump", dur=0.6),
}
RESERVED = {"type", "at", "until", "dur", "layer", "place", "in", "out", "sfx", "x", "y", "anchor", "attach", "corner",
            "w", "dx", "dy", "id", "mute_captions", "zone"}
TIME_KEYS = ("at", "strike", "badge_at", "scroll_at", "click_at", "on_at", "roll_at", "draw_at", "open_at")
MUTED = ("cta", "hook", "punch")          # captions are hidden while these are on screen


def _localize(obj, t0, words, duration):
    """Inside props, absolute time refs (at/strike/…) become seconds relative to the item start (key `t`)."""
    if isinstance(obj, list):
        return [_localize(x, t0, words, duration) for x in obj]
    if not isinstance(obj, dict):
        return obj
    out = {}
    for k, v in obj.items():
        if k in TIME_KEYS and isinstance(v, (int, float, str)):
            name = "t" if k == "at" else {"strike": "strike_t"}.get(k, k.replace("_at", "_t"))
            out[name] = max(0.0, at(v, words, duration) - t0) if not (isinstance(v, str) and v.startswith("+")) \
                else float(v[1:])
        else:
            out[k] = _localize(v, t0, words, duration)
    return out


def _logos(p, base_dir, style):
    if not isinstance(p, dict):
        return p
    q = {}
    for k, v in p.items():
        if k == "logo":
            q[k] = L.resolve(v, base_dir, style)
        elif isinstance(v, list):
            q[k] = [_logos(x, base_dir, style) for x in v]
        elif isinstance(v, dict):
            q[k] = _logos(v, base_dir, style)
        else:
            q[k] = v
    return q


def _paths(p, base_dir):
    """Image paths in props (src/image), relative to the plan → file:// URIs Chromium can open."""
    for k in ("src", "image"):
        v = p.get(k)
        if isinstance(v, str) and v and not re.match(r"^(data|https?|file):", v):
            f = Path(v).expanduser()
            f = f if f.is_absolute() else Path(base_dir) / f
            if f.exists():
                p[k] = f.resolve().as_uri()
    return p


def build(overlays, words, duration, segs, base_dir, logo_style="tile"):
    items, mutes = [], []
    seg_at = lambda t: next((s for s in reversed(segs) if s["t0"] <= t + 1e-6), segs[0])
    for n, o in enumerate(overlays or ()):
        typ = o.get("type", "html")
        d = T.get(typ, T["html"])
        dflt = d["dur"] if d["dur"] is not None else max(0.5, duration - at(o.get("at", 0), words, duration))
        t0, t1 = span(o, words, duration, default_dur=dflt)
        seg = seg_at(t0)
        props = {k: v for k, v in o.items() if k not in RESERVED}
        props = _paths(_logos(_localize(props, t0, words, duration), base_dir, logo_style), base_dir)
        if typ in ("repo",) and not props.get("logo"):
            props["logo"] = L.resolve("github", base_dir, logo_style)
        it = {
            "id": o.get("id", f"i{n}"), "type": typ, "t0": round(t0, 4), "t1": round(t1, 4),
            "layer": o.get("layer", "over" if seg["mode"] == "full" else d["layer"]), "place": o.get("place", d["place"]),
            "in": list(o.get("in", d["inn"])) if not isinstance(o.get("in"), str) else [o["in"], d["inn"][1] or 0.3],
            "out": list(o.get("out", d["out"])) if not isinstance(o.get("out"), str) else [o["out"], 0.2],
            "sfx": o.get("sfx", d["sfx"]), "props": props, "zone": {**seg["zone"], **o.get("zone", {})}, "zid": seg["zid"],
        }
        for k in ("x", "y", "anchor", "attach", "corner", "w", "dx", "dy"):
            if k in o and typ == "hearts" and k in ("x", "y"):
                props[k] = o[k]                  # where the hearts start, not where the full-screen layer goes
            elif k in o:
                it[k] = o[k]
        if typ == "hook" and seg["mode"] in ("full", "split") and props.get("style") != "box" and o.get("scrim", True):
            items.append({"id": f"scrim{n}", "type": "scrim", "t0": it["t0"], "t1": it["t1"], "layer": "over",
                          "place": "full", "in": ["fade", 0.25], "out": ["fade", 0.25], "sfx": None,
                          "props": {"side": "top", "height": 860}, "zone": it["zone"], "zid": it["zid"]})
        if typ == "title" and seg["zone"].get("capOn") == "bg":
            props.setdefault("style", "on-bg")
        if typ == "marker":
            props.setdefault("on_bg", seg["mode"] in ("sticker", "pip", "broll"))
        if o.get("mute_captions", typ in MUTED):
            mutes.append([it["t0"], it["t1"]])
        items.append(it)
    # attached items must be positioned after their targets
    items.sort(key=lambda i: 1 if i.get("attach") else 0)
    return items, mutes
