"""Overlay renderer: headless Chromium draws the cards/captions layer for each frame (transparent PNG)."""
import base64
import json
import os
from pathlib import Path

import cv2
import numpy as np

from ..themes import css_vars
from ..util import ASSETS

HERE = Path(__file__).resolve().parent
EMPTY, SAME = "empty", "same"


def chromium_args():
    exe = os.environ.get("SHORTS_CHROMIUM")
    return {"executable_path": exe} if exe else {}


def write_html(tl, theme, layer, path):
    data = dict(tl, layer=layer)
    html = f"""<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="{(ASSETS / 'fonts' / 'fonts.css').as_uri()}">
<link rel="stylesheet" href="{(HERE / 'style.css').as_uri()}">
<style>{css_vars(theme)}</style></head>
<body class="theme-{theme['name']}"><div id="stage"></div>
<script>window.TL = {json.dumps(data, ensure_ascii=False)};</script>
<script src="{(HERE / 'runtime.js').as_uri()}"></script></body></html>"""
    Path(path).write_text(html, encoding="utf8")
    return Path(path)


class Pages:
    """One browser, one page per layer; frame(t) → {layer: EMPTY | SAME | RGBA uint8 array}."""

    def __init__(self, html_paths, scale=1.0):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch(**chromium_args())
        self.pages, self.prev, self.cdp = {}, {}, {}
        self.size = (round(1080 * scale), round(1920 * scale))
        for layer, path in html_paths.items():
            pg = self.browser.new_page(viewport={"width": 1080, "height": 1920}, device_scale_factor=scale)
            errs = []
            pg.on("pageerror", lambda e, errs=errs: errs.append(str(e)))
            pg.goto(Path(path).as_uri())
            pg.evaluate("window.__ready")
            if errs:
                raise RuntimeError(f"error en la capa «{layer}»: {errs[0]}")
            cdp = pg.context.new_cdp_session(pg)
            cdp.send("Emulation.setDefaultBackgroundColorOverride", {"color": {"r": 0, "g": 0, "b": 0, "a": 0}})
            self.pages[layer], self.cdp[layer], self.prev[layer] = pg, cdp, None

    def events(self):
        return next(iter(self.pages.values())).evaluate("window.__events()")

    def sizes(self):
        return next(iter(self.pages.values())).evaluate("window.__ready")

    def frame(self, t):
        out = {}
        for layer, pg in self.pages.items():
            sig = pg.evaluate("t => window.__frame(t)", t)
            if sig == "":
                out[layer] = EMPTY
                self.prev[layer] = ""
            elif sig == self.prev[layer]:
                out[layer] = SAME
            else:
                data = self.cdp[layer].send("Page.captureScreenshot", {"format": "png", "optimizeForSpeed": True})["data"]
                img = cv2.imdecode(np.frombuffer(base64.b64decode(data), np.uint8), cv2.IMREAD_UNCHANGED)
                if (img.shape[1], img.shape[0]) != self.size:      # some Chromium builds ignore a scale < 1 (draft)
                    img = cv2.resize(img, self.size, interpolation=cv2.INTER_AREA)
                out[layer] = img[..., [2, 1, 0, 3]] if img.shape[2] == 4 else np.dstack([img[..., ::-1], np.full(img.shape[:2], 255, np.uint8)])
                self.prev[layer] = sig
        return out

    def close(self):
        try:
            self.browser.close()
            self._pw.stop()
        except Exception:
            pass


def render_html_png(tiles, out):
    """Small helper for `python -m shorts logo …`: draw resolved logos side by side."""
    from playwright.sync_api import sync_playwright
    from ..themes import theme
    th = theme("claro")
    cells = "".join(f"<div class='c'><div id='t{i}'></div><p>{n}</p></div>" for i, (n, _) in enumerate(tiles))
    html = f"""<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="{(ASSETS / 'fonts' / 'fonts.css').as_uri()}"><link rel="stylesheet" href="{(HERE / 'style.css').as_uri()}">
<style>{css_vars(th)} html,body{{width:auto;height:auto;background:#F1EEE6}} .g{{display:flex;flex-wrap:wrap;gap:30px;padding:30px;width:1080px}}
.c{{text-align:center;width:150px;font:600 20px Inter}}</style></head><body><div class="g">{cells}</div>
<script>window.TL={{W:1080,H:1920,layer:'x',items:[],layout:[],captions:{{chunks:[]}}}};</script>
<script src="{(HERE / 'runtime.js').as_uri()}"></script>
<script>const L={json.dumps([t for _, t in tiles])};L.forEach((x,i)=>{{document.getElementById('t'+i).innerHTML=window.__tile(x,120)}});</script>
</body></html>"""
    tmp = Path(out).with_suffix(".html")
    tmp.write_text(html, encoding="utf8")
    with sync_playwright() as p:
        b = p.chromium.launch(**chromium_args())
        pg = b.new_page(viewport={"width": 1080, "height": 400})
        pg.goto(tmp.resolve().as_uri())
        pg.evaluate("document.fonts.ready")
        pg.screenshot(path=str(out), full_page=True)
        b.close()
    tmp.unlink(missing_ok=True)
