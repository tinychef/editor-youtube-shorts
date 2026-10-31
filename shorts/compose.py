"""Frame compositor: background → cards (under) → speaker (frame / cut-out + white border) → captions (over)."""
import math

import cv2
import numpy as np

from .themes import hex_rgb


def _ss(x, a, b):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


_GRID = {}


def rrect_sdf(W, H, rect, radius, roi=None):
    """Signed distance to a rounded rect (negative inside), evaluated on the canvas (or a ROI)."""
    x, y, w, h = rect
    r = max(0.0, min(radius, w / 2, h / 2))
    y0, y1, x0, x1 = roi or (0, H, 0, W)
    if (W, H) not in _GRID:
        _GRID[(W, H)] = (np.arange(H, dtype=np.float32)[:, None], np.arange(W, dtype=np.float32)[None, :])
    gy, gx = _GRID[(W, H)]
    yy, xx = gy[y0:y1], gx[:, x0:x1]
    cx, cy = x + w / 2, y + h / 2
    qx = np.abs(xx + 0.5 - cx) - (w / 2 - r)
    qy = np.abs(yy + 0.5 - cy) - (h / 2 - r)
    out = np.sqrt(np.maximum(qx, 0) ** 2 + np.maximum(qy, 0) ** 2) + np.minimum(np.maximum(qx, qy), 0) - r
    return out


def _lut(a, b):
    x = np.arange(256, dtype=np.float32) / 255
    return (_ss(x, a, b) * 255 + 0.5).astype(np.uint8)


LUT_MATTE = _lut(0.3, 0.7)        # crisp the soft matte edge
LUT_OUTLINE = _lut(0.38, 0.62)    # round die-cut outline


class Overlay:
    """Cached premultiplied overlay restricted to its non-transparent bounding box."""

    def __init__(self):
        self.roi = None

    def set(self, rgba):
        a = rgba[..., 3]
        ys, xs = np.nonzero(a > 0)
        if len(ys) == 0:
            self.roi = None
            return
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        sub = rgba[y0:y1, x0:x1].astype(np.float32)
        al = sub[..., 3:4] * (1 / 255)
        self.roi = (y0, y1, x0, x1)
        self.pm = np.ascontiguousarray(sub[..., :3] * al)
        self.inv = np.ascontiguousarray(np.repeat(1 - al, 3, axis=2))

    def clear(self):
        self.roi = None

    def apply(self, canvas):
        if self.roi is None:
            return
        y0, y1, x0, x1 = self.roi
        c = canvas[y0:y1, x0:x1]
        np.multiply(c, self.inv, out=c)
        np.add(c, self.pm, out=c)


def _shifted(P):
    """Layout params moved by P["shift"] (slide transitions)."""
    sx, sy = P.get("shift", (0.0, 0.0))
    if not sx and not sy:
        return P
    x, y, w, h = P["rect"]
    return {**P, "ax": P["ax"] + sx, "ay": P["ay"] + sy, "rect": (x + sx, y + sy, w, h)}


class Composer:
    def __init__(self, W, H, bg, theme, src_size, matte_size, scale=1.0):
        """bg: a themes.Backdrop (animated or not) or a static float RGB image (0..1)."""
        self.W, self.H, self.k = W, H, scale
        if isinstance(bg, np.ndarray):
            bg = _Static((bg * 255).astype(np.float32))
        self.bg = bg
        self.Sw, self.Sh = src_size
        self.mw, self.mh = matte_size
        sp = theme["speaker"]
        self.outline_rgb = np.array(hex_rgb(sp.get("outline", "#FFFFFF")), np.float32)
        self.hard = sp.get("hard_shadow")
        # fade at the matte's left/right/top borders so a body cut by the camera frame never shows a straight edge
        fx = np.minimum(np.arange(self.mw), np.arange(self.mw)[::-1]).astype(np.float32)
        fy = np.arange(self.mh).astype(np.float32)
        ramp = max(4, int(self.mw * 0.03))
        edge = np.clip(fx / ramp, 0, 1)[None, :] * np.clip(fy / ramp, 0, 1)[:, None]
        self.edge8 = (edge * 255 + 0.5).astype(np.uint8)

    def speaker(self, canvas, frame, matte, P):
        """Draw the speaker onto canvas (float32 HxWx3, 0..1) in place."""
        k, W, H = self.k, self.W, self.H
        P = _shifted(P)
        vis = P["vis"]
        if vis <= 0.002:
            return
        s = P["scale"] * k
        ax, ay = P["ax"] * k, (P["ay"] + P["dy"]) * k
        fx, fy = P["fx"], P["fy"]
        fh, fw = frame.shape[:2]
        sx, sy = self.Sw / fw, self.Sh / fh            # frames may be read at reduced size (draft)
        M = np.float32([[s * sx, 0, ax - fx * s], [0, s * sy, ay - fy * s]])
        rx, ry, rw, rh = (v * k for v in P["rect"])
        room, pop = P["room"], P["pop"]
        need_person = pop > 0.002 or room < 0.998
        # canvas region touched by the frame (everything else is untouched)
        x0 = int(max(0, np.floor(ax - fx * s))); x1 = int(min(W, np.ceil(ax + (self.Sw - fx) * s)))
        y0 = int(max(0, np.floor(ay - fy * s))); y1 = int(min(H, np.ceil(ay + (self.Sh - fy) * s)))
        if x1 <= x0 or y1 <= y0:
            return
        pad = int(P["outline"] * k + 44 * k)
        sm = s * self.Sw / self.mw, s * self.Sh / self.mh
        if room < 0.002:
            # cut-out only: work inside the person's bounding box, not the whole screen
            rows = np.flatnonzero(matte.max(axis=1) > 40)
            cols = np.flatnonzero(matte.max(axis=0) > 40)
            if not len(rows):
                return
            x0 = max(x0, int(ax - fx * s + cols[0] * sm[0]))
            x1 = min(x1, int(ax - fx * s + (cols[-1] + 1) * sm[0]) + 1)
            y0 = max(y0, int(ay - fy * s + rows[0] * sm[1]))
            y1 = min(y1, int(ay - fy * s + (rows[-1] + 1) * sm[1]) + 1)
            if x1 <= x0 or y1 <= y0:
                return
        X0, X1, Y0, Y1 = max(0, x0 - pad), min(W, x1 + pad), max(0, y0 - pad), min(H, y1 + pad)
        ow, oh = X1 - X0, Y1 - Y0
        Mr = M.copy()
        Mr[0, 2] -= X0
        Mr[1, 2] -= Y0
        img = cv2.warpAffine(frame, Mr, (ow, oh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        img = img.astype(np.float32)
        roi = (Y0, Y1, X0, X1)
        rect_full = rx <= 0.5 and ry <= 0.5 and rw >= W - 1 and rh >= H - 1 and P["radius"] < 0.5
        if rect_full:
            rm = None
            sdf = None
        else:
            sdf = rrect_sdf(W, H, (rx, ry, rw, rh), P["radius"] * k, roi)
            rm = np.clip(0.5 - sdf, 0, 1)
        c = canvas[Y0:Y1, X0:X1]
        zero = np.zeros_like(c)

        def over(src, a):          # c ← src·a + c·(1−a)
            a = np.ascontiguousarray(a, dtype=np.float32)
            c[:] = cv2.blendLinear(src, np.ascontiguousarray(c), a, 1 - a)

        # frame drop shadow (split/popout/pip)
        if sdf is not None and P["frame_shadow"] > 0.01 and room > 0.01:
            sh = np.clip(1 - np.maximum(rrect_sdf(W, H, (rx, ry + 18 * k, rw, rh), P["radius"] * k, roi), 0) / (46 * k), 0, 1) ** 2
            over(zero, P["frame_shadow"] * room * vis * sh * (1 - rm))
        if need_person:
            mM = np.float32([[sm[0], 0, M[0, 2] - X0], [0, sm[1], M[1, 2] - Y0]])
            m8 = cv2.multiply(matte, self.edge8, scale=1 / 255)
            a8 = cv2.LUT(cv2.warpAffine(m8, mM, (ow, oh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT), LUT_MATTE)
            al = a8.astype(np.float32) * (1 / 255)
            pm = al if rm is None else al * (rm + (1 - rm) * pop)
            if vis < 0.999:
                pm = pm * vis
            ol = P["outline"] * k
            if ol >= 0.75 or P["shadow"] > 0.01 or self.hard:
                if ol >= 0.75:
                    b = (pm > 0.5).astype(np.uint8)
                    dist = cv2.distanceTransform(1 - b, cv2.DIST_L2, 5)
                    o8 = (np.clip(ol + 0.5 - dist, 0, 1) * 255).astype(np.uint8)
                    o8 = cv2.LUT(cv2.GaussianBlur(o8, (0, 0), max(1.0, ol * 0.33)), LUT_OUTLINE)
                    o = o8.astype(np.float32) * (1 / 255)
                    if P.get("outline_scope") == "outside" and sdf is not None:
                        o *= np.clip(sdf / 3 + 0.5, 0, 1)
                    o = np.maximum(o, pm)
                    if vis < 0.999:
                        o *= vis
                else:
                    o = pm
                if self.hard and room < 0.5:
                    dx, dy, col = self.hard
                    Mt = np.float32([[1, 0, dx * k], [0, 1, dy * k]])
                    hs = cv2.warpAffine(o, Mt, (ow, oh)) * (1 - room)
                    over(np.full_like(c, 0) + np.array(hex_rgb(col), np.float32), hs)   # pixel-style hard shadow
                elif P["shadow"] > 0.01:
                    # soft drop shadow, blurred at 1/4 resolution (same look, far cheaper)
                    small = cv2.resize(o, (max(1, ow // 4), max(1, oh // 4)), interpolation=cv2.INTER_AREA)
                    small = cv2.GaussianBlur(small, (0, 0), 4 * k)
                    Mt = np.float32([[1, 0, 0], [0, 1, 14 * k / 4]])
                    small = cv2.warpAffine(small, Mt, (small.shape[1], small.shape[0]))
                    sh = cv2.resize(small, (ow, oh), interpolation=cv2.INTER_LINEAR)
                    over(zero, P["shadow"] * sh)
                if ol >= 0.75:
                    ring = o - pm
                    np.clip(ring, 0, 1, out=ring)
                    over(self._fill(c), ring)
        # room (the original background inside the frame)
        if room > 0.002:
            if rm is None and room * vis >= 0.999:
                c[:] = img
            else:
                over(img, (np.ones((oh, ow), np.float32) if rm is None else rm) * (room * vis))
        if need_person:
            over(img, pm)
        if P["border"] > 0.5 and sdf is not None:
            bw = P["border"] * k
            ring = np.clip(0.5 - (np.abs(sdf + bw / 2) - bw / 2), 0, 1) * vis
            over(np.full_like(c, 255.0), ring)

    def _fill(self, like):
        if getattr(self, "_white", None) is None or self._white.shape != like.shape:
            self._white = np.empty_like(like)
            self._white[:] = self.outline_rgb
        return self._white

    def frame(self, frame, matte, P, under, over, progress=None, prog_color=None, t=0.0):
        canvas = self.bg.frame(t)
        under.apply(canvas)
        if P.get("also"):                         # slide transition: the outgoing layout first
            self.speaker(canvas, frame, matte, P["also"])
        self.speaker(canvas, frame, matte, P)
        over.apply(canvas)
        if progress is not None:
            h = max(2, int(10 * self.k))
            canvas[:h, : int(self.W * progress)] = prog_color * 255
        if P.get("zoomfx") is not None:
            canvas = self.zoom_blur(canvas, P["zoomfx"])
        return cv2.convertScaleAbs(canvas)

    def zoom_blur(self, canvas, x):
        """Zoom transition: the whole frame pushes in and radially blurs up to the cut (x = 0.5), then settles."""
        bump = math.sin(math.pi * min(max(x, 0.0), 1.0))
        if bump < 0.01:
            return canvas
        W, H = self.W, self.H
        s = 1 + 0.18 * bump
        M = cv2.getRotationMatrix2D((W / 2, H / 2), 0, s)
        sharp = cv2.warpAffine(canvas, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        # radial blur at quarter resolution: the average of slightly bigger copies of the frame
        w4, h4 = max(2, W // 4), max(2, H // 4)
        small = cv2.resize(canvas, (w4, h4), interpolation=cv2.INTER_AREA)
        acc = np.zeros_like(small)
        n = 6
        for j in range(n):
            Mj = cv2.getRotationMatrix2D((w4 / 2, h4 / 2), 0, s * (1 + 0.035 * bump * j))
            acc += cv2.warpAffine(small, Mj, (w4, h4), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
        acc = cv2.GaussianBlur(acc * (1 / n), (0, 0), 1.0 + 2.5 * bump)
        blur = cv2.resize(acc, (W, H), interpolation=cv2.INTER_LINEAR)
        a = min(1.0, bump * 1.8)
        return cv2.addWeighted(sharp, 1 - a, blur, a, 0)


class _Static:
    def __init__(self, img):
        self.img = img

    def frame(self, t):
        return self.img.copy()
