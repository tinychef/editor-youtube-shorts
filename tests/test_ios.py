"""Pruebas del tema ios (predeterminado), su fondo animado, las transiciones nuevas y los motion graphics."""
import re
from pathlib import Path

import numpy as np
import pytest

from shorts import audio, captions, layout, timeline
from shorts.themes import Backdrop, background, darken, hex_rgb, theme

ROOT = Path(__file__).resolve().parent.parent
W = [{"w": w, "s": s, "e": e, "p": 0.9, "i": i} for i, (w, s, e) in enumerate([
    ("Esto", 0.1, 0.3), ("es", 0.3, 0.4), ("gratis", 0.45, 0.9), ("y", 1.0, 1.1), ("muy", 1.2, 1.4), ("importante.", 1.5, 2.1)])]


def test_ios_es_el_tema_predeterminado():
    th = theme(None)
    assert th["name"] == "ios"
    v = th["vars"]
    assert v["--accent"] == "#FF0069" and v["--on-accent"] == "#FFFFFF" and v["--accent-text"] == "#D6005C"
    assert v["--card"] == "#FFFFFF" and v["--muted"] == "#8E8E93" and v["--line"] == "#C6C6C8"
    assert v["--danger"] == "#FF3B30" and v["--success"] == "#34C759"
    assert v["--card-shadow"] == "0 8px 24px rgba(0,0,0,.08)" and "rgba(60,60,67,.12)" in v["--card-border"]
    assert 24 <= int(v["--radius"].rstrip("px")) <= 28
    for c in ("#FF7A00", "#FF0069", "#D300C5", "#7638FA"):
        assert c in v["--grad"]
    assert v["--cta-bg"] == "var(--grad)"           # el degradado solo en destacados


def test_tipografia_de_apple_con_respaldo_inter():
    v = theme("ios")["vars"]
    for k in ("--font-ui", "--font-display", "--font-cap"):
        stack = v[k]
        assert stack.startswith("-apple-system") and "SF Pro" in stack and "Inter" in stack
        assert stack.index("SF Pro") < stack.index("Inter")
    assert "SF Pro Display" in v["--font-display"] and "SF Pro Text" in v["--font-ui"]
    css = (ROOT / "assets" / "fonts" / "fonts.css").read_text()
    assert "'Inter Var'" in css and "font-weight: 100 900" in css
    # no se incluyen archivos de SF Pro (licencia de Apple)
    assert not [f for f in (ROOT / "assets").rglob("*") if re.search(r"sf.?pro", f.name, re.I)]


def test_acento_personalizado_oscurece_el_texto():
    th = theme({"base": "ios", "accent": "#0A84FF"})
    assert th["vars"]["--accent"] == "#0A84FF"
    assert th["vars"]["--accent-text"] == darken("#0A84FF")
    assert sum(hex_rgb(th["vars"]["--accent-text"])) < sum(hex_rgb("#0A84FF"))


def test_fondo_gris_ios_con_puntos():
    th = theme("ios")
    assert th["bg"]["color"] == "#F2F2F7" and th["bg"]["dot_color"] == "#C7C7CC"
    assert th["bg"]["cell"] == 28 and th["bg"]["dot"] == pytest.approx(2.2) and th["bg"]["scroll"] == 40
    img = Backdrop(th, 1080, 1920).frame(0.0)
    assert img.shape == (1920, 1080, 3) and img.dtype == np.float32
    assert np.allclose(img.max(axis=(0, 1)), hex_rgb("#F2F2F7"), atol=0.5)       # fondo
    assert np.allclose(img.min(axis=(0, 1)), hex_rgb("#C7C7CC"), atol=1.5)       # centro de los puntos chicos


def test_fondo_se_mueve_hacia_arriba_y_en_bucle():
    th = theme({"base": "ios", "bg": {"parallax": 0}})
    B = Backdrop(th, 280, 280)
    a, b = B.frame(0.0), B.frame(1 / 30)
    assert np.abs(a - b).mean() > 0.1                                             # se mueve cada cuadro
    assert np.allclose(a, B.frame(28 / 40), atol=1e-3)                            # un periodo = sin salto

    def dot_y(img):            # centroide vertical de la primera columna de puntos
        col = 242 - img[:28, :, 1].min(axis=1)
        return float((np.arange(28) * col).sum() / col.sum())
    up = dot_y(B.frame(0.0)) - dot_y(B.frame(0.1))
    assert up == pytest.approx(4.0, abs=0.3)                                      # 40 px/s hacia arriba
    down = Backdrop(theme({"base": "ios", "bg": {"parallax": 0, "scroll": -40}}), 280, 280)
    assert dot_y(down.frame(0.1)) - dot_y(down.frame(0.0)) == pytest.approx(4.0, abs=0.3)


def test_parallax_va_a_media_velocidad():
    B = Backdrop(theme("ios"), 280, 280)
    L = {l["cell"]: l for l in B.layers}
    assert set(L) == {28, 56}
    assert L[56]["speed"] == pytest.approx(L[28]["speed"] / 2) and L[56]["r"] > L[28]["r"] and L[56]["alpha"] < 1
    assert np.allclose(B.frame(0.0), B.frame(56 / 20), atol=1e-3)                 # bucle del conjunto
    assert not np.allclose(B.frame(0.0), B.frame(28 / 40), atol=1e-3)             # la capa grande va más lenta


def test_temas_estaticos_no_cambian():
    for name in ("claro", "oscuro", "tonyciencia"):
        th = theme(name)
        B = Backdrop(th, 216, 384)
        assert not B.layers
        assert np.allclose(B.frame(3.0), background(th, 216, 384) * 255, atol=1e-3)


def test_transiciones_zoom_y_deslizamiento():
    segs = layout.resolve([{"at": 0, "mode": "full"}, {"at": 2.0, "mode": "sticker", "transition": "zoom"},
                           {"at": 4.0, "mode": "split", "transition": "slide", "dir": "up"}], W, 6.0, 1080, 1920)
    track = {k: [v] * 180 for k, v in (("face_x", 0.5), ("face_y", 0.4), ("face_h", 0.17), ("head_top", 0.28))}
    sp = layout.Speaker(segs, track, (1080, 1920), 1080, 1920, 30, [0.0], theme("ios"))
    early, late = sp.params(61), sp.params(70)                  # 2.03 s y 2.33 s (zoom de 0.42 s)
    assert early["mode"] == "full" and late["mode"] == "sticker"  # corte duro escondido en el desenfoque
    assert 0 < early["zoomfx"] < 0.5 < late["zoomfx"] < 1
    assert "zoomfx" not in sp.params(80)
    P = sp.params(123)                                          # 4.1 s: deslizamiento hacia arriba
    assert P["mode"] == "split" and P["also"]["mode"] == "sticker"
    assert P["shift"][0] == 0 and P["shift"][1] > 0 and P["also"]["shift"][1] < 0
    with pytest.raises(SystemExit):
        layout.resolve([{"at": 0, "mode": "full", "transition": "giro"}], W, 6.0, 1080, 1920)


def test_motion_graphics_en_la_linea_de_tiempo(tmp_path):
    (tmp_path / "captura.png").write_bytes(b"x")
    segs = layout.resolve([{"at": 0, "mode": "sticker"}], W, 6.0, 1080, 1920)
    items, mutes = timeline.build([
        {"type": "notif", "at": "w:0", "title": "Claude", "text": "Hola"},
        {"type": "punch", "at": "w:2", "text": "GRATIS"},
        {"type": "confetti", "at": "w:2+0.5", "x": 540, "y": 700},
        {"type": "toggle", "at": 1.0, "label": "Modo gratis", "on_at": "w:3"},
        {"type": "odometer", "at": 1.0, "to": "$1,037", "roll_at": 1.5},
        {"type": "marker", "at": "w:4", "text": "muy importante", "draw_at": "w:5"},
        {"type": "iphone", "at": 2.0, "src": "captura.png"},
        {"type": "hearts", "at": 3.0, "x": 700, "y": 1300}], W, 6.0, segs, tmp_path)
    by = {i["type"]: i for i in items}
    assert by["notif"]["layer"] == "over" and by["notif"]["place"] == "top" and by["notif"]["in"][0] == "drop"
    assert by["punch"]["place"] == "full" and by["punch"]["t1"] - by["punch"]["t0"] == pytest.approx(0.6)
    assert [round(m[0], 2) for m in mutes] == [0.45]                  # sin subtítulos durante la palabra golpe
    assert by["confetti"]["layer"] == "under"                          # las partículas caen detrás de la persona
    assert by["toggle"]["props"]["on_t"] == pytest.approx(0.0) and by["odometer"]["props"]["roll_t"] == pytest.approx(0.5)
    assert by["marker"]["props"]["draw_t"] == pytest.approx(0.3) and by["marker"]["props"]["on_bg"] is True
    assert by["iphone"]["props"]["src"].startswith("file://")
    assert by["hearts"]["layer"] == "over" and by["hearts"]["place"] == "full"
    assert by["hearts"]["props"]["x"] == 700 and "y" not in by["hearts"]          # origen de los corazones


def test_subrayado_en_subtitulos():
    c = captions.build(W, {"marker": ["importante"], "emphasis": ["gratis"]}, 3.0)
    flat = {w["w"]: w for ch in c["chunks"] for w in ch["words"]}
    assert flat["importante"]["m"] and not flat["gratis"]["m"] and flat["gratis"]["e"]


def test_sonidos_nuevos():
    for name in ("haptic", "softpop", "bubble", "sparkle", "notif", "ratchet", "marker"):
        y = audio.synth(name, 1.0)
        assert name in audio.GAIN_DB and len(y) > 100 and np.isfinite(y).all() and np.abs(y).max() <= 1.05


def test_animaciones_puras_sin_css_animado():
    css = (ROOT / "shorts" / "overlay" / "style.css").read_text()
    js = (ROOT / "shorts" / "overlay" / "runtime.js").read_text()
    assert "@keyframes" not in css and not re.search(r"(^|[;{\s])transition\s*:", css)
    assert "Math.random" not in js and "Date.now" not in js and "performance.now" not in js
    assert "'visible'" not in js          # un hijo «visible» se vería también en la copia oculta de la otra capa
    for comp in ("notif", "imessage", "toggle", "rings", "chart", "odometer", "hearts", "confetti", "punch", "marker",
                 "homescreen", "island", "iphone"):
        assert f"C.{comp} =" in js and comp in timeline.T
