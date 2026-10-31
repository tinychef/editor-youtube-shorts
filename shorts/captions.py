"""Captions: 2–3 words at a time, phrased on punctuation and pauses, keywords in the accent color."""
import re
import unicodedata

from .util import at

PUNCT_END = re.compile(r"[.,;:!?…]$")


def _norm(s):
    s = unicodedata.normalize("NFD", s.lower())
    return re.sub(r"[^a-z0-9$%]", "", "".join(c for c in s if not unicodedata.combining(c)))


def apply_fixes(words, fixes, replace=()):
    """fixes: {"Cloud": "Claude"} whole-word, case-insensitive, keeps trailing punctuation.
    replace: [{"w": [31, 33], "text": "la suscripción"}] rewrites a run of words (timing is spread)."""
    fx = {_norm(k): v for k, v in (fixes or {}).items()}
    out = []
    for w in words:
        m = re.match(r"^(.*?)([.,;:!?…]*)$", w["w"])
        core, tail = m.group(1), m.group(2)
        rep = fx.get(_norm(core))
        out.append({**w, "w": (rep + tail) if rep is not None else w["w"]})
    for r in replace or ():
        a, b = r["w"]
        new = str(r["text"]).split()
        if not new or not (0 <= a <= b < len(out)):
            continue
        s, e = out[a]["s"], out[b]["e"]
        span = [dict(out[a], w=x) for x in new]
        for k, x in enumerate(span):
            x["s"] = s + (e - s) * k / len(span)
            x["e"] = s + (e - s) * (k + 1) / len(span)
        out[a:b + 1] = span
        for i, x in enumerate(out):
            x["i"] = i
    return out


def build(words, style, duration, mute=()):
    """→ {"chunks": [{t0, t1, words: [{w, t0, t1, e}]}], "mute": [[a, b]], "style": {...}}"""
    st = {"max_words": 3, "max_chars": 20, "emphasis": [], "auto_emphasis": True, "case": None, "strip": ".,;:",
          "karaoke": False, "pop": True, "marker": []}
    st.update(style or {})
    if st.get("enabled") is False or not words:
        return {"chunks": [], "mute": [], "style": st}
    emph = {_norm(x) for x in st["emphasis"] for x in [x] if x}
    emph_phr = [x for x in st["emphasis"] if " " in x]
    marked = {_norm(x) for x in st["marker"] if x}
    chunks, cur = [], []

    def close():
        if cur:
            chunks.append(cur[:])
            cur.clear()

    for i, w in enumerate(words):
        txt = w["w"]
        n = _norm(txt)
        is_e = n in emph or (st["auto_emphasis"] and bool(re.search(r"\d", txt)))
        disp = txt.rstrip(st["strip"]) if st["strip"] else txt
        if st["case"] == "upper":
            disp = disp.upper()
        elif st["case"] == "lower":
            disp = disp.lower()
        gap = w["s"] - words[i - 1]["e"] if i else 0
        chars = sum(len(x["w"]) + 1 for x in cur) + len(disp)
        if cur and (len(cur) >= st["max_words"] or chars > st["max_chars"] or gap > 0.32):
            close()
        cur.append({"w": disp, "t0": w["s"], "t1": w["e"], "e": is_e, "m": n in marked})
        if PUNCT_END.search(txt) and txt[-1] in ".!?…:":
            close()
    close()
    # emphasis (and marker) by phrase ("código abierto")
    for ph in emph_phr + [x for x in st["marker"] if " " in x]:
        toks = [_norm(x) for x in ph.split()]
        for ch in chunks:
            ns = [_norm(x["w"]) for x in ch]
            for k in range(len(ns) - len(toks) + 1):
                if ns[k:k + len(toks)] == toks:
                    for x in ch[k:k + len(toks)]:
                        if ph in st["marker"]:
                            x["m"] = True
                        else:
                            x["e"] = True
    out = []
    for k, ch in enumerate(chunks):
        t0 = ch[0]["t0"]
        nxt = chunks[k + 1][0]["t0"] if k + 1 < len(chunks) else duration
        t1 = nxt if nxt - ch[-1]["t1"] < 0.7 else ch[-1]["t1"] + 0.3
        out.append({"t0": round(t0, 3), "t1": round(min(t1, duration), 3), "words": ch})
    return {"chunks": out, "mute": [list(m) for m in mute], "style": st}


def mute_spans(spec, words, duration):
    res = []
    for a, b in spec or ():
        res.append([at(a, words, duration), at(b, words, duration)])
    return res
