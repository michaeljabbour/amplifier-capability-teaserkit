"""An original soundtrack synthesized from scratch: warm detuned pad, soft plucked arpeggio,
sub bass, and a small feedback-delay room. No samples, so nothing is borrowed or licensed.

Deterministic: the same (seconds, bpm, seed, progression) always produces the same file.
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SR = 48000

# (bass root, chord tones) as MIDI note numbers
PROGRESSIONS: dict[str, list[tuple[int, list[int]]]] = {
    "warm": [(36, [48, 52, 55, 59]), (45, [45, 48, 52, 55]), (41, [41, 45, 48, 52]), (43, [43, 47, 50, 52])],   # Cmaj7 Am7 Fmaj7 G6
    "bright": [(38, [50, 54, 57, 61]), (47, [47, 50, 54, 57]), (43, [43, 47, 50, 54]), (45, [45, 49, 52, 54])],  # Dmaj7 Bm7 Gmaj7 A6
    "calm": [(33, [45, 48, 52, 55]), (41, [41, 45, 48, 52]), (36, [48, 52, 55, 59]), (43, [43, 47, 50, 55])],    # Am7 Fmaj7 Cmaj7 G
}


def _midi(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def _env(length: int, a: float, r: float) -> np.ndarray:
    e = np.ones(length)
    ai, ri = min(int(a * SR), length // 2), min(int(r * SR), length // 2)
    if ai:
        e[:ai] = np.linspace(0, 1, ai) ** 1.5
    if ri:
        e[-ri:] *= np.linspace(1, 0, ri) ** 1.5
    return e


def synthesize(seconds: float, *, bpm: float = 96, seed: int = 7, progression: str = "warm", peak_db: float = -4.0) -> np.ndarray:
    """Return stereo float samples in [-1, 1], shape (n, 2), exactly `seconds` long at 48 kHz."""
    if seconds <= 0:
        raise ValueError("seconds must be positive")
    chords = PROGRESSIONS.get(progression)
    if chords is None:
        raise ValueError(f"unknown progression {progression!r}; choose from {', '.join(PROGRESSIONS)}")
    n = int(round(seconds * SR))
    L, R = np.zeros(n), np.zeros(n)
    beat = 60.0 / bpm
    bar = 4 * beat
    rng = np.random.default_rng(seed)
    for b in range(int(np.ceil(seconds / bar)) + 1):
        root, tones = chords[b % len(chords)]
        s0 = int(b * bar * SR)
        if s0 >= n:
            break
        length = min(n - s0, int((bar + 1.2) * SR))
        tt = np.arange(length) / SR
        env = _env(length, 0.9, 1.4)
        for m in tones:  # pad: detuned pairs an octave up
            f = _midi(m + 12)
            for det, pan in ((-0.12, 0.35), (0.12, 0.65)):
                ff = f * 2 ** (det / 12)
                v = (np.sin(2 * np.pi * ff * tt + rng.uniform(0, 6)) + 0.18 * np.sin(4 * np.pi * ff * tt)) * env * 0.045
                L[s0:s0 + length] += v * (1 - pan)
                R[s0:s0 + length] += v * pan
        fb = _midi(root)  # sub bass
        benv = _env(length, 0.05, 1.0) * np.exp(-tt * 0.35)
        bass = (np.sin(2 * np.pi * fb * tt) + 0.25 * np.sin(4 * np.pi * fb * tt)) * benv * 0.11
        L[s0:s0 + length] += bass
        R[s0:s0 + length] += bass
        if b >= 1:  # plucked eighth-note arpeggio after the intro bar
            for k, idx in enumerate([0, 2, 1, 3, 2, 1, 3, 2]):
                ps = s0 + int(k * beat / 2 * SR)
                if ps >= n:
                    break
                pl = min(n - ps, int(1.4 * SR))
                pt = np.arange(pl) / SR
                f = _midi(tones[idx] + 24)
                pe = np.exp(-pt * 5.5) * np.minimum(1, pt / 0.004)
                v = (np.sin(2 * np.pi * f * pt) + 0.3 * np.sin(4 * np.pi * f * pt) * np.exp(-pt * 9)) * pe * 0.055
                pan = 0.3 if k % 2 == 0 else 0.7
                L[ps:ps + pl] += v * (1 - pan)
                R[ps:ps + pl] += v * pan
    d = int(0.21 * SR)  # room
    for buf in (L, R):
        for rep, g in ((1, 0.28), (2, 0.12)):
            if d * rep < n:
                buf[d * rep:] += buf[:-d * rep].copy() * g
    mix = np.stack([L, R], 1)
    fi, fo = min(n, int(0.6 * SR)), min(n, int(min(2.0, seconds / 6) * SR))
    if fi:
        mix[:fi] *= np.linspace(0, 1, fi)[:, None]
    if fo:
        mix[-fo:] *= (np.linspace(1, 0, fo) ** 1.3)[:, None]
    mix /= np.max(np.abs(mix)) + 1e-9
    return mix * 10 ** (peak_db / 20)


def write_wav(samples: np.ndarray, path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    pcm = (np.clip(samples, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(p), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return p


def make_track(seconds: float, out: str | Path, *, bpm: float = 96, seed: int = 7, progression: str = "warm") -> dict:
    """Synthesize a duration-matched track and write it as 48 kHz 16-bit stereo WAV."""
    p = write_wav(synthesize(seconds, bpm=bpm, seed=seed, progression=progression), out)
    return {"path": str(p), "seconds": round(seconds, 3), "bpm": bpm, "seed": seed, "progression": progression}


def wav_seconds(path: str | Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / w.getframerate()
