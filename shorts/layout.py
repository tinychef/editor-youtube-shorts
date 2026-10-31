"""Speaker layouts and their geometry.

Modes (what the plan's "layout" timeline switches between):
  full     the speaker fills the screen (hooks, emphasis)
  split    hard split: graphics on top, speaker video in the bottom part
  sticker  the speaker cut out with a white border over the theme background, graphics on top  ← default
  popout   speaker in a rounded frame at the bottom; head and hands break out of the frame
  pip      small rounded speaker in a corner over full-screen graphics
  broll    graphics only, speaker hidden

Every mode is one point in the same parameter space (frame rect, scale, anchor, room, pop, outline…),
so switching modes is a smooth interpolation, never a hard swap.
"""
from .util import at, clamp, ease_in_out, lerp, smooth

MODES = ("full", "split", "sticker", "popout", "pip", "broll")
DEFAULT_TRANS = 0.32
# how a layout change animates: morph (interpolate the geometry), zoom (push in + radial blur, cut at the
# midpoint) or slide (the new layout pushes the old one off the screen)
TRANSITIONS = {"morph": DEFAULT_TRANS, "zoom": 0.42, "slide": 0.45}
SLIDE_DIRS = {"left": (-1, 0), "right": (1, 0), "up": (0, -1), "down": (0, 1)}


def zone(mode, W, H, opt=None):
    """Where overlays go for each mode: card stack area, title line, caption line."""
    o = opt or {}
    if mode == "full":
        return {"mode": mode, "top": [1000, 1400], "title": 330, "cap": 1310, "capOn": "speaker"}
    if mode == "split":
        r = o.get("split", 0.5)
        return {"mode": mode, "top": [170, r * H - 40], "title": r * H, "cap": r * H + 150, "capOn": "speaker"}
    if mode == "popout":
        top = o.get("frame_top", 0.6) * H
        return {"mode": mode, "top": [170, top - 190], "title": 470, "cap": top + 360, "capOn": "speaker"}
    if mode == "pip":
        return {"mode": mode, "top": [170, 1220], "title": 520, "cap": 1400, "capOn": "bg"}
    if mode == "broll":
        return {"mode": mode, "top": [170, 1330], "title": 600, "cap": 1450, "capOn": "bg"}
    # sticker
    head = o.get("head_y", 0.47) * H
    return {"mode": mode, "top": [170, head - 30], "title": head * 0.55, "cap": min(1440, head + 540), "capOn": "speaker"}


def resolve(plan_layout, words, duration, W, H, default="sticker"):
    """Plan layout keyframes → contiguous segments with zones (output time)."""
    keys = plan_layout or [{"at": 0, "mode": default}]
    segs = []
    for k in keys:
        mode = k.get("mode", default)
        if mode not in MODES:
            raise SystemExit(f"layout: modo «{mode}» no existe (usa {', '.join(MODES)})")
        if k.get("transition", "morph") not in TRANSITIONS:
            raise SystemExit(f"layout: transición «{k['transition']}» no existe (usa {', '.join(TRANSITIONS)})")
        t0 = at(k.get("at", 0), words, duration)
        opt = {kk: v for kk, v in k.items() if kk not in ("at", "mode")}
        segs.append({"t0": max(0.0, t0), "mode": mode, "opt": opt})
    segs.sort(key=lambda s: s["t0"])
    segs[0]["t0"] = 0.0
    for a, b in zip(segs, segs[1:] + [None]):
        a["t1"] = b["t0"] if b else float(duration)
    segs = [s for s in segs if s["t1"] - s["t0"] > 1e-3]
    for i, s in enumerate(segs):
        s["zone"] = {**zone(s["mode"], W, H, s["opt"]), **s["opt"].get("zone", {})}
        s["zid"] = i
    return segs


class Speaker:
    """Per-frame speaker geometry from the layout segments, the face track and the cut list."""

    def __init__(self, segs, track, src_size, W, H, fps, shots, theme, zooms=(), cut_zoom=None):
        self.segs, self.tr, self.W, self.H, self.fps = segs, track, W, H, fps
        self.Sw, self.Sh = src_size
        self.shots = sorted(shots)
        self.th = theme["speaker"]
        self.zooms = zooms
        self.cut_zoom = cut_zoom

    def _track(self, i):
        tr = self.tr
        i = min(max(i, 0), len(tr["face_x"]) - 1)
        return (tr["face_x"][i] * self.Sw, tr["face_y"][i] * self.Sh, tr["face_h"][i] * self.Sh,
                tr["head_top"][i] * self.Sh)

    def _shot_index(self, t):
        n = 0
        for s in self.shots:
            if s <= t + 1e-6:
                n += 1
        return max(0, n - 1)

    def _zoom(self, t, mode, opt):
        z = float(opt.get("zoom", 1.0))
        cz = opt.get("cut_zoom", self.cut_zoom)
        if cz is None:
            cz = {"full": 1.09, "split": 1.08, "popout": 1.05, "sticker": 1.04}.get(mode, 1.0)
        if cz and self._shot_index(t) % 2 == 1:
            z *= cz
        for zz in self.zooms:
            a, b, s = zz["t0"], zz["t1"], zz["scale"]
            ramp = min(0.22, (b - a) / 3)
            k = smooth((t - a) / ramp) * (1 - smooth((t - (b - ramp)) / ramp))
            z *= 1 + (s - 1) * k
        return z

    def mode_params(self, mode, opt, i, t):
        W, H, Sw, Sh = self.W, self.H, self.Sw, self.Sh
        fx, fy, fh, ht = self._track(i)
        z = self._zoom(t, mode, opt)
        th = self.th
        P = {"rect": (0.0, 0.0, float(W), float(H)), "radius": 0.0, "room": 1.0, "pop": 0.0, "outline": 0.0,
             "shadow": 0.0, "vis": 1.0, "frame_shadow": 0.0, "border": 0.0, "dy": 0.0}

        def cover(rx, ry, rw, rh, s, ax, ay, free_top=False):
            # keep the frame covering the rect (no empty bands); with free_top the top may open (pop-out)
            if Sw * s >= rw:
                left = ax - fx * s
                if left > rx:
                    ax -= left - rx
                right = ax - fx * s + Sw * s
                if right < rx + rw:
                    ax += rx + rw - right
            else:
                ax = rx + rw / 2 - (Sw / 2 - fx) * s
            bot = ay - fy * s + Sh * s
            if bot < ry + rh:
                ay += ry + rh - bot
            top = ay - fy * s
            if not free_top and top > ry:
                ay -= top - ry
            return ax, ay

        if mode in ("full", "broll"):
            s = max(W / Sw, H / Sh) * z
            ax, ay = cover(0, 0, W, H, s, W / 2, opt.get("face_y", 0.36) * H)
            P.update(scale=s, ax=ax, ay=ay)
            if mode == "broll":
                P.update(vis=0.0, dy=160.0)
        elif mode == "split":
            r = opt.get("split", 0.5)
            ry = r * H
            rh = H - ry
            s = max(W / Sw, rh / Sh) * z
            ax, ay = cover(0, ry, W, rh, s, W / 2, ry + opt.get("face_y", 0.42) * rh)
            P.update(scale=s, ax=ax, ay=ay, rect=(0.0, ry, float(W), rh), radius=float(opt.get("radius", 0)))
        elif mode == "popout":
            m = opt.get("margin", 110)
            ry = opt.get("frame_top", 0.6) * H
            rect = (float(m), ry, float(W - 2 * m), H - ry - m)
            s = max(rect[2] / Sw, rect[3] / Sh) * z
            head = ry - opt.get("pop_px", 0.075 * H)
            ax, ay = cover(*rect, s, W / 2, head + (fy - ht) * s, free_top=True)
            ol = opt.get("outline", 0)
            P.update(scale=s, ax=ax, ay=ay, rect=rect, radius=float(opt.get("radius", 44)), pop=1.0,
                     outline=float(th["outline_px"] if ol is True else ol or 0), outline_scope="outside",
                     frame_shadow=th.get("frame_shadow", 0.3))
        elif mode == "pip":
            d = opt.get("size", 380)
            rect = (W - d - 54.0, H - d - 300.0, float(d), float(d))
            s = max(d / Sw, d / Sh) * 1.5 * z
            ax, ay = cover(*rect, s, rect[0] + d / 2, rect[1] + d * 0.45)
            P.update(scale=s, ax=ax, ay=ay, rect=rect, radius=d / 2, border=8.0, frame_shadow=0.35)
        else:  # sticker
            portrait = Sh >= Sw
            s = (W / Sw if portrait else (0.15 * H) / max(fh, 1)) * opt.get("scale", 1.0)
            s = min(s, opt.get("max_face", 0.2) * H / max(fh, 1)) * z     # tight selfies: leave room for captions
            head = opt.get("head_y", 0.47) * H
            ay = head + (fy - ht) * s
            if ay + (Sh - fy) * s < H:            # never let the torso float above the bottom edge
                ay = H - (Sh - fy) * s
            ax = W / 2 + opt.get("dx", 0)
            if (Sw * s) >= W:
                left = ax - fx * s
                if left > 0:
                    ax -= left
                right = ax + (Sw - fx) * s
                if right < W:
                    ax += W - right
            ol = opt.get("outline", True)
            P.update(scale=s, ax=ax, ay=ay, room=0.0, pop=1.0,
                     outline=float(th["outline_px"] if ol is True else (ol or 0)),
                     shadow=float(opt.get("shadow", th.get("shadow", 0.28))))
        P["fx"], P["fy"] = fx, fy
        return P

    def params(self, i):
        t = i / self.fps
        k = 0
        for j, s in enumerate(self.segs):
            if s["t0"] <= t + 1e-9:
                k = j
        cur = self.segs[k]
        P = self.mode_params(cur["mode"], cur["opt"], i, t)
        P["mode"] = cur["mode"]
        kind = cur["opt"].get("transition", "morph")
        trans = cur["opt"].get("trans", TRANSITIONS.get(kind, DEFAULT_TRANS))
        if k > 0 and trans > 0 and t - cur["t0"] < trans:
            prev = self.segs[k - 1]
            Q = self.mode_params(prev["mode"], prev["opt"], i, t)
            Q["mode"] = prev["mode"]
            x = (t - cur["t0"]) / trans
            if kind == "zoom":
                P = dict(Q if x < 0.5 else P, zoomfx=x)       # the blur hides the hard switch
            elif kind == "slide":
                ux, uy = SLIDE_DIRS.get(cur["opt"].get("dir", "left"), (-1, 0))
                e = ease_in_out(x)
                P = dict(P, shift=((1 - e) * -ux * self.W, (1 - e) * -uy * self.H),
                         also=dict(Q, shift=(e * ux * self.W, e * uy * self.H)))
            else:
                P = blend(Q, P, ease_in_out(x))
        return P


def blend(A, B, e):
    out = dict(B)
    for key in ("scale", "ax", "ay", "radius", "room", "pop", "outline", "shadow", "vis", "frame_shadow", "border",
                "dy", "fx", "fy"):
        out[key] = lerp(A.get(key, 0.0), B.get(key, 0.0), e)
    out["rect"] = tuple(lerp(a, b, e) for a, b in zip(A["rect"], B["rect"]))
    if A.get("outline", 0) > B.get("outline", 0):
        out["outline_scope"] = A.get("outline_scope", "all")
    return out


def transitions(segs):
    """Times where the layout changes (for a whoosh)."""
    return [s["t0"] for s in segs[1:]]


def clamp01(x):
    return clamp(x)
