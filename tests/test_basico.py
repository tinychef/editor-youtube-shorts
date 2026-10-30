"""Pruebas rápidas sin modelos ni video: cortes, tiempos, subtítulos, diseños y logos."""
from shorts import captions, cuts, layout, timeline
from shorts.util import at

W = [{"w": w, "s": s, "e": e, "p": 0.9} for w, s, e in [
    ("Deja", 0.10, 0.30), ("de", 0.30, 0.40), ("pagar", 0.42, 0.80), ("eh", 1.60, 1.80),
    ("Número", 2.50, 2.90), ("uno,", 2.90, 3.20), ("Claude.", 3.25, 3.80), ("Comenta", 5.00, 5.40), ("IA", 5.45, 5.70)]]


def test_cortes_quitan_pausas_y_muletillas():
    r = cuts.keep_ranges(W, 6.0, 30)
    words, dur = cuts.remap(W, r)
    assert "eh" not in [w["w"] for w in words]
    assert dur < 4.0                                    # 6 s de video → sin pausas largas
    for s, e, _ in r:                                    # bordes en la rejilla de cuadros
        assert abs(s * 30 - round(s * 30)) < 1e-6 and abs(e * 30 - round(e * 30)) < 1e-6
    assert [w["i"] for w in words] == list(range(len(words)))


def test_drop_quita_una_toma():
    r = cuts.keep_ranges(W, 6.0, 30, drop=[(4, 6)])
    words, _ = cuts.remap(W, r)
    assert "Claude." not in [w["w"] for w in words]


def test_referencias_de_tiempo():
    words, dur = cuts.remap(W, cuts.keep_ranges(W, 6.0, 30))
    assert at("w:0", words, dur) == words[0]["s"]
    assert at("w:1.e", words, dur) == words[1]["e"]
    assert abs(at("w:2+0.5", words, dur) - (words[2]["s"] + 0.5)) < 1e-9
    assert at("end", words, dur) == dur


def test_subtitulos_y_correcciones():
    fixed = captions.apply_fixes(W, {"claude": "Claude"}, [{"w": [7, 8], "text": "Comenta IA"}])
    c = captions.build(fixed, {"emphasis": ["Claude"]}, 6.0)
    flat = [w for ch in c["chunks"] for w in ch["words"]]
    assert any(w["w"] == "Claude" and w["e"] for w in flat)        # énfasis, sin el punto final
    assert all(len(ch["words"]) <= 3 for ch in c["chunks"])
    assert all(a["t1"] <= b["t0"] + 1e-9 for a, b in zip(c["chunks"], c["chunks"][1:]))


def test_disenos_y_zonas():
    segs = layout.resolve([{"at": 0, "mode": "full"}, {"at": 2.0, "mode": "sticker"}], W, 6.0, 1080, 1920)
    assert [s["mode"] for s in segs] == ["full", "sticker"] and segs[-1]["t1"] == 6.0
    for m in layout.MODES:
        z = layout.zone(m, 1080, 1920)
        assert 0 < z["cap"] <= 1530 and z["top"][0] < z["top"][1]


def test_timeline_capas_y_mute():
    segs = layout.resolve([{"at": 0, "mode": "full"}, {"at": 2.0, "mode": "sticker"}], W, 6.0, 1080, 1920)
    items, mutes = timeline.build([
        {"type": "hook", "at": 0, "until": 1.8, "lines": ["A", "B"]},
        {"type": "app", "at": 2.5, "until": 4.0, "name": "X", "logo": {"text": "X", "bg": "#000"}},
        {"type": "cta", "at": 5.0, "until": "end", "keyword": "IA"}], W, 6.0, segs, ".")
    app = next(i for i in items if i["type"] == "app")
    assert app["layer"] == "under" and app["place"] == "stack"
    assert any(i["type"] == "scrim" for i in items)        # el gancho en full lleva degradado
    assert [round(m[0], 2) for m in mutes] == [0.0, 5.0]   # sin subtítulos durante gancho y CTA
