"""Stage 1 · prepare: transcribe, cut pauses/fillers/retakes, and analyse the person (matte + tracking).

Everything lands in work/<name>/:
  words_src.json  words with source times (from Whisper, refined)
  cut.json        kept ranges + the options used (re-run with --drop to remove retakes)
  cut.mkv         the cut video at constant fps (no audio)
  voice.wav       the cut voice track (48 kHz, sample-accurate joins)
  words.json      kept words in OUTPUT time, re-indexed — plans refer to them as "w:N"
  transcript.txt  readable transcript with word indices, for planning the edit
  matte.mkv       person matte (gray, analysis resolution)
  track.json      face/head positions per frame (smoothed per shot)
  meta.json       sizes, fps, duration
"""
from pathlib import Path

from . import cuts as C
from .matte import analyze
from .transcribe import DEFAULT_MODEL, extract_audio, transcribe
from .util import log, probe, read_json, slug, write_json


def parse_drop(spec):
    """'12-30,45-47' → [(12, 30), (45, 47)] (word indices of the ORIGINAL transcript, inclusive)."""
    out = []
    for part in (spec or "").replace(" ", "").split(","):
        if not part:
            continue
        a, _, b = part.partition("-")
        out.append((int(a), int(b or a)))
    return out


def prepare(video, work="work", name=None, language="es", model=DEFAULT_MODEL, vocab="", drop="",
            max_pause=0.20, fillers=True, quality="hq", fps=30, recut=False):
    video = Path(video).resolve()
    if not video.exists():
        raise SystemExit(f"No existe {video}")
    info = probe(video)
    if not info["audio"]:
        raise SystemExit("El video no tiene audio: el editor se guía por lo que dices.")
    wd = Path(work) / (name or slug(video.stem))
    wd.mkdir(parents=True, exist_ok=True)
    log(f"{video.name}: {info['width']}x{info['height']} · {info['fps']:.2f} fps · {info['duration']:.1f} s → {wd}")

    src = read_json(wd / "words_src.json")
    if src is None or src.get("video") != str(video) or src.get("model") != model or not recut:
        extract_audio(video, wd / "audio16k.wav")
        tr = transcribe(wd / "audio16k.wav", language=language, model=model, vocab=vocab)
        src = {"video": str(video), "model": model, "language": tr["language"], "words": tr["words"]}
        write_json(wd / "words_src.json", src)
        (wd / "audio16k.wav").unlink(missing_ok=True)
    words = src["words"]
    if not words:
        raise SystemExit("Whisper no encontró voz en el video.")
    (wd / "transcript_src.txt").write_text(C.transcript_text([{**w, "i": i} for i, w in enumerate(words)]),
                                           encoding="utf8")

    drops = parse_drop(drop)
    ranges = C.keep_ranges(words, info["duration"], fps, max_pause=max_pause, fillers=fillers, drop=drops)
    C.summary(words, ranges, info["duration"])
    C.cut_video(video, ranges, wd / "cut.mkv", fps)
    dur_a = C.cut_audio(video, ranges, wd / "voice.wav")
    out_words, dur = C.remap(words, ranges)
    cut_info = probe(wd / "cut.mkv")
    write_json(wd / "cut.json", {"ranges": [[s, e] for s, e, _ in ranges], "drop": drops, "max_pause": max_pause,
                                 "fillers": fillers})
    write_json(wd / "words.json", out_words)
    (wd / "transcript.txt").write_text(C.transcript_text(out_words), encoding="utf8")
    shot_starts, t = [], 0.0
    for s, e, _ in ranges:
        shot_starts.append(round(t, 4))
        t += e - s
    expected = sum(int(round((e - s) * fps)) for s, e, _ in ranges)
    n = analyze(wd / "cut.mkv", (cut_info["width"], cut_info["height"]), fps, shot_starts, wd, quality, frames=expected)
    meta = {"source": str(video), "source_info": info, "fps": fps, "size": [cut_info["width"], cut_info["height"]],
            "frames": n, "duration": round(n / fps, 4), "audio_duration": round(dur_a, 4), "shots": shot_starts,
            "language": src["language"], "words": len(out_words)}
    write_json(wd / "meta.json", meta)
    log(f"listo: {wd / 'transcript.txt'} ({len(out_words)} palabras, {meta['duration']:.1f} s)")
    return wd
