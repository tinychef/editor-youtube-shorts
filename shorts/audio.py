"""Sound: voice polish, synthesized UI sound effects on every card/pop/strike, optional ducked music,
and a -14 LUFS master (YouTube Shorts' loudness target). All effects are generated here — no licenses."""
import json
import re

import numpy as np

from .util import log, run

SR = 48000
RNG = np.random.default_rng(7)


def _env(n, a, d):
    """attack/decay envelope in samples."""
    e = np.ones(n, np.float32)
    a = max(1, int(a))
    e[:a] = np.linspace(0, 1, a)
    if d:
        e[a:] = np.exp(-np.arange(n - a) / max(1.0, d))
    return e


def _bandnoise(n, f_lo, f_hi, f_lo2=None, f_hi2=None):
    """Noise whose pass band slides from [f_lo, f_hi] to [f_lo2, f_hi2] (STFT shaping)."""
    from scipy.signal import istft, stft
    x = RNG.standard_normal(n + 2048).astype(np.float32)
    f, t, Z = stft(x, SR, nperseg=1024)
    k = np.linspace(0, 1, Z.shape[1])[None, :]
    lo = f_lo + ((f_lo2 or f_lo) - f_lo) * k
    hi = f_hi + ((f_hi2 or f_hi) - f_hi) * k
    F = f[:, None]
    mask = np.clip((F - lo) / (0.25 * lo + 1), 0, 1) * np.clip((hi - F) / (0.25 * hi + 1), 0, 1)
    _, y = istft(Z * mask, SR, nperseg=1024)
    y = y[:n].astype(np.float32)
    return y / (np.abs(y).max() + 1e-9)


def _sine(n, f0, f1=None, phase=0.0):
    f = np.linspace(f0, f1 if f1 else f0, n, dtype=np.float32)
    return np.sin(phase + 2 * np.pi * np.cumsum(f) / SR).astype(np.float32)


def _bell(dur, f0, amp=1.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = np.zeros(n, np.float32)
    for r, a, d in ((1, 1, 0.9), (2.0, 0.35, 0.5), (2.76, 0.4, 0.35), (5.4, 0.18, 0.15), (8.93, 0.08, 0.08)):
        y += a * np.sin(2 * np.pi * f0 * r * t) * np.exp(-t / d)
    return amp * y * _env(n, 0.002 * SR, 0) / 1.6


def synth(name, dur=0.0):
    """Mono float32 effect at 48 kHz, peak ≈ 1 (gains applied by the mixer)."""
    if name == "pop":
        n = int(0.13 * SR)
        y = _sine(n, 1350, 420) * _env(n, 0.002 * SR, 0.028 * SR)
        y += 0.25 * _bandnoise(n, 2000, 9000) * _env(n, 1, 0.004 * SR)
        return y
    if name in ("whoosh", "swoosh"):
        d = 0.42 if name == "whoosh" else 0.26
        n = int(d * SR)
        x = np.linspace(0, 1, n)
        e = (np.sin(np.pi * x ** 0.7) ** 2).astype(np.float32)
        return _bandnoise(n, 300, 1200, 1600, 6000) * e
    if name == "rise":
        n = int(0.7 * SR)
        x = np.linspace(0, 1, n)
        e = (x ** 2.2 * (1 - np.clip((x - 0.92) / 0.08, 0, 1))).astype(np.float32)
        return (0.7 * _bandnoise(n, 400, 1500, 2500, 9000) + 0.3 * _sine(n, 220, 880)) * e
    if name == "click":
        n = int(0.03 * SR)
        return 0.6 * _bandnoise(n, 1500, 7000) * _env(n, 1, 0.003 * SR) + 0.5 * _sine(n, 3400) * _env(n, 1, 0.006 * SR)
    if name == "tick":
        n = int(0.025 * SR)
        return _sine(n, 2600) * _env(n, 1, 0.004 * SR) + 0.3 * _bandnoise(n, 3000, 9000) * _env(n, 1, 0.002 * SR)
    if name == "type":
        d = max(0.15, dur)
        n = int(d * SR)
        y = np.zeros(n + SR // 10, np.float32)
        t = 0.0
        while t < d:
            k = int(t * SR)
            m = int(0.02 * SR)
            c = _bandnoise(m, 1200 + RNG.uniform(-300, 600), 6500) * _env(m, 1, 0.003 * SR) * RNG.uniform(0.5, 1.0)
            y[k:k + m] += c
            t += RNG.uniform(0.045, 0.11)
        return y[:n]
    if name == "count":
        return synth("type", dur) * 0.6
    if name == "ding":
        return _bell(1.2, 1568)
    if name == "cash":
        n = int(1.0 * SR)
        y = np.zeros(n, np.float32)
        for t0 in (0.0, 0.06):
            m = int(0.05 * SR)
            k = int(t0 * SR)
            y[k:k + m] += 0.6 * _bandnoise(m, 3500, 9000) * _env(m, 1, 0.012 * SR)
        k = int(0.11 * SR)
        b = _bell(0.85, 1318.5) + 0.8 * _bell(0.85, 1975.5)
        y[k:k + len(b)] += 0.7 * b[: n - k]
        return y
    if name == "thump":
        n = int(0.35 * SR)
        y = _sine(n, 120, 48) * _env(n, 0.001 * SR, 0.07 * SR)
        y += 0.5 * _bandnoise(n, 80, 1200) * _env(n, 1, 0.02 * SR)
        return y
    if name == "buzz":
        n = int(0.22 * SR)
        sq = np.sign(_sine(n, 104)) * 0.6
        from scipy.signal import butter, lfilter
        b, a = butter(2, 1400 / (SR / 2))
        y = lfilter(b, a, sq).astype(np.float32)
        gate = ((np.arange(n) / SR) % 0.11 < 0.075).astype(np.float32)
        return y * gate * _env(n, 0.003 * SR, 0)
    if name == "success":
        a = _bell(0.6, 1046.5)
        b = _bell(0.8, 1568)
        y = np.zeros(int(0.9 * SR), np.float32)
        y[: len(a)] += a
        k = int(0.12 * SR)
        y[k:k + len(b)] += b[: len(y) - k]
        return y
    return np.zeros(1, np.float32)


GAIN_DB = {"pop": -17, "whoosh": -21, "swoosh": -23, "rise": -22, "click": -18, "tick": -27, "type": -24, "count": -28,
           "ding": -19, "cash": -17, "thump": -12, "buzz": -26, "success": -19}


def sfx_track(events, duration, volume=1.0, t_from=0.0):
    n = int((duration + 1.5) * SR)
    L = np.zeros(n, np.float32)
    R = np.zeros(n, np.float32)
    last = {}
    for ev in events:
        name, t = ev["sfx"], ev["t"] - t_from
        if name not in GAIN_DB or t < -0.05 or t > duration:
            continue
        if t - last.get(name, -9) < (0.06 if name in ("pop", "tick") else 0.12):   # avoid machine-gun stacking
            continue
        last[name] = t
        y = synth(name, ev.get("dur", 0.0)) * (10 ** (GAIN_DB[name] / 20)) * volume
        lead = 0.12 if name in ("whoosh", "swoosh") else 0.0       # a whoosh peaks where the card lands
        k = int(max(0.0, t - lead) * SR)
        y = y[: max(0, n - k)]
        pan = ev.get("pan", 0.0)
        L[k:k + len(y)] += y * np.sqrt(0.5 * (1 - pan))
        R[k:k + len(y)] += y * np.sqrt(0.5 * (1 + pan))
    return np.stack([L, R], 1)[: int(duration * SR)]


def voice_chain(src_wav, out_wav, denoise=False, t_from=0.0, duration=None):
    chain = ["highpass=f=80", "equalizer=f=220:t=q:w=1.1:g=-1.5", "equalizer=f=3600:t=q:w=1.3:g=2",
             "acompressor=threshold=0.09:ratio=3:attack=5:release=120:makeup=1.6", "alimiter=limit=0.92:level=0"]
    if denoise:
        chain.insert(1, "afftdn=nr=12:nf=-42")
    trim = ["-ss", f"{t_from:.4f}"] + (["-t", f"{duration:.4f}"] if duration else [])
    run(["ffmpeg", "-y", "-v", "error", *trim, "-i", src_wav, "-af", ",".join(chain), "-ar", str(SR), "-ac", "1",
         "-c:a", "pcm_f32le", out_wav])


def load(path, ch=2):
    p = run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", str(ch), "-ar", str(SR), "-f", "f32le", "-"], text=False)
    return np.frombuffer(p.stdout, np.float32).reshape(-1, ch).copy()


def music_bed(path, voice, duration, level_db=-20.0, duck_db=-9.0):
    m = load(path)
    n = int(duration * SR)
    if len(m) == 0:
        return np.zeros((n, 2), np.float32)
    while len(m) < n:
        m = np.concatenate([m, m])
    m = m[:n]
    rms = np.sqrt(np.mean(m ** 2) + 1e-12)
    m *= (10 ** (level_db / 20)) / rms * 0.25
    # duck under the voice: 20 ms RMS, fast attack, slow release
    hop = int(0.02 * SR)
    v = voice[: n // hop * hop, 0] if voice.ndim == 2 else voice[: n // hop * hop]
    e = np.sqrt((v.reshape(-1, hop) ** 2).mean(1))
    act = (20 * np.log10(e + 1e-7) > -38).astype(np.float32)
    g = np.zeros_like(act)
    a_att, a_rel = 1 - np.exp(-1 / 3), 1 - np.exp(-1 / 20)
    for i in range(len(act)):
        prev = g[i - 1] if i else 0.0
        g[i] = prev + (a_att if act[i] > prev else a_rel) * (act[i] - prev)
    gain = 10 ** (duck_db * g / 20)
    gain = np.repeat(gain, hop)
    gain = np.pad(gain, (0, max(0, n - len(gain))), constant_values=gain[-1] if len(gain) else 1)[:n]
    fade = np.ones(n, np.float32)
    fi, fo = int(0.4 * SR), int(1.2 * SR)
    fade[:fi] = np.linspace(0, 1, fi)
    fade[-fo:] = np.linspace(1, 0, fo)
    return m * (gain * fade)[:, None]


def master(mix, out_wav, target=-14.0):
    import soundfile as sf
    tmp = str(out_wav) + ".pre.wav"
    sf.write(tmp, mix, SR, subtype="FLOAT")
    p = run(["ffmpeg", "-v", "info", "-i", tmp, "-af", f"loudnorm=I={target}:TP=-1.0:LRA=11:print_format=json",
             "-f", "null", "-"])
    m = json.loads(re.findall(r"\{[^{}]+\}", p.stderr)[-1])
    af = (f"loudnorm=I={target}:TP=-1.0:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
          f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    run(["ffmpeg", "-y", "-v", "error", "-i", tmp, "-af", af, "-ar", str(SR), "-c:a", "pcm_s24le", str(out_wav)])
    import os
    os.remove(tmp)
    return float(m["input_i"])


def build(work, events, duration, plan, base_dir, out_wav, t_from=0.0):
    voice_p = str(out_wav) + ".voice.wav"
    voice_chain(work / "voice.wav", voice_p, denoise=plan.get("denoise", False), t_from=t_from, duration=duration)
    v = load(voice_p, 1)[:, 0]
    n = int(duration * SR)
    v = np.pad(v, (0, max(0, n - len(v))))[:n]
    mix = np.stack([v, v], 1) * 0.92
    sfx = plan.get("sfx", {})
    if sfx is not False and (not isinstance(sfx, dict) or sfx.get("enabled", True)):
        vol = sfx.get("volume", 1.0) if isinstance(sfx, dict) else 1.0
        mix += sfx_track(events, duration, vol, t_from)[:n]
    mu = plan.get("music")
    if mu and (mu.get("file") if isinstance(mu, dict) else mu):
        path = mu["file"] if isinstance(mu, dict) else mu
        mp = (base_dir / path) if not str(path).startswith("/") else path
        if not mp.exists():
            log(f"música: no existe {mp}, sigo sin música")
        else:
            lvl = mu.get("level", -20) if isinstance(mu, dict) else -20
            mix += music_bed(mp, v, duration, lvl, mu.get("duck", -9) if isinstance(mu, dict) else -9)
    import os
    os.remove(voice_p)
    li = master(mix, out_wav)
    log(f"audio: {li:.1f} LUFS → -14 LUFS, pico -1 dBTP")
