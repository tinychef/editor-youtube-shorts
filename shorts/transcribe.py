"""Word-level transcription with faster-whisper (local, CPU or GPU) plus energy-based boundary refinement."""
import hashlib
import os
import time
from pathlib import Path

import numpy as np

from .util import CACHE, log, read_json, run, write_json

# Names Whisper tends to mangle in Spanish («Cloud» for Claude, «Gip» for GIMP…). Passed as hotwords.
VOCAB = ("Claude, Claude Code, Anthropic, ChatGPT, OpenAI, Gemini, Google, GitHub, Notion, Canva, Figma, "
         "Midjourney, Perplexity, Cursor, Copilot, n8n, Make, Zapier, WhatsApp, Instagram, TikTok, YouTube, "
         "Shorts, Excel, Photoshop, Premiere, CapCut, DaVinci, Higgsfield, ElevenLabs, Runway, Sora, Veo, "
         "Kling, Supabase, Vercel, Cloudflare, Stripe, Shopify, prompt, prompts, skill, skills, repo, repos")

DEFAULT_MODEL = os.environ.get("SHORTS_WHISPER", "large-v3-turbo")


def extract_audio(video, wav, sr=16000):
    run(["ffmpeg", "-y", "-v", "error", "-i", video, "-vn", "-ac", "1", "-ar", str(sr), "-c:a", "pcm_s16le", wav])


def load_wav(path):
    import soundfile as sf
    a, sr = sf.read(str(path), dtype="float32", always_2d=False)
    if a.ndim > 1:
        a = a.mean(axis=1)
    return a, sr


def transcribe(wav, language="es", model=DEFAULT_MODEL, vocab="", cache=True):
    audio, sr = load_wav(wav)
    assert sr == 16000, "transcribe() espera audio a 16 kHz"
    hot = ", ".join(x for x in (VOCAB, vocab) if x)
    key = hashlib.sha1(audio.tobytes() + f"{model}|{language}|{hot}|v3".encode()).hexdigest()[:16]
    cpath = CACHE / "transcripts" / f"{key}.json"
    if cache and cpath.exists():
        log("transcripción: en caché")
        out = read_json(cpath)
        out["words"] = drop_hallucinations(out["words"])
        return out
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise SystemExit("Falta faster-whisper: pip install -r requirements.txt")
    t = time.time()
    log(f"transcribiendo con Whisper «{model}» (la primera vez descarga el modelo)…")
    try:
        import ctranslate2
        device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
    except Exception:
        device = "cpu"
    wm = WhisperModel(model, device=device, compute_type="float16" if device == "cuda" else "int8",
                      cpu_threads=max(1, os.cpu_count() or 4))
    segs, info = wm.transcribe(audio, language=language or None, word_timestamps=True, beam_size=5,
                               vad_filter=False, hotwords=hot or None, condition_on_previous_text=False)
    words = []
    for s in segs:
        for w in s.words or []:
            txt = w.word.strip()
            if txt:
                words.append({"w": txt, "s": round(float(w.start), 3), "e": round(float(w.end), 3),
                              "p": round(float(w.probability), 3)})
    words = refine(words, audio, sr)
    out = {"language": info.language, "model": model, "words": words}
    write_json(cpath, out)
    out["words"] = drop_hallucinations(words)
    log(f"transcripción: {len(words)} palabras en {time.time() - t:.0f} s")
    return out


def drop_hallucinations(words):
    """Whisper invents «Thanks.» / «Gracias.» on silence: near-zero confidence words go, and so do
    low-confidence words trailing at the very end."""
    words = [w for w in words if w.get("p", 1) >= 0.02]
    while words and words[-1].get("p", 1) < 0.2:
        words.pop()
    return words


def envelope(audio, sr, hop=0.01):
    n = int(sr * hop)
    k = len(audio) // n
    fr = audio[: k * n].reshape(k, n)
    return 20 * np.log10(np.sqrt((fr ** 2).mean(axis=1)) + 1e-7)


def refine(words, audio, sr, hop=0.01):
    """Snap word edges to where the voice actually starts/stops so cuts don't clip syllables."""
    if not words:
        return words
    env = envelope(audio, sr, hop)
    floor = np.percentile(env, 8)
    thr = min(max(floor + 12, -52), -30)
    loud = env > thr
    n = len(env)

    def idx(t):
        return int(min(max(t / hop, 0), n - 1))

    out = []
    for i, w in enumerate(words):
        s, e = w["s"], max(w["e"], w["s"] + 0.04)
        a, b = idx(s - 0.12), idx(min(s + max(0.25, 0.8 * (e - s)), e - 0.03))
        hit = np.nonzero(loud[a:b + 1])[0]
        if len(hit):
            s2 = (a + hit[0]) * hop
            if s2 < e - 0.03:
                s = s2
        a, b = idx(max(e - 0.25, s)), idx(e + 0.18)
        hit = np.nonzero(loud[a:b + 1])[0]
        if len(hit):
            e = max(s + 0.04, (a + hit[-1] + 1) * hop)
        if out and s < out[-1]["e"]:
            s = out[-1]["e"]
            e = max(e, s + 0.04)
        out.append({**w, "s": round(s, 3), "e": round(e, 3)})
    return out


def words_from_text(words):
    return " ".join(w["w"] for w in words)
