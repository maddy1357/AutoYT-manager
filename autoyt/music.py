"""Procedural background music.

Every note is synthesised here from sine/triangle waves and noise, so the result is original
audio with no third-party samples or melodies: nothing for Content ID to match against.
"""
import wave
from pathlib import Path

import numpy as np

SR = 44100

# (root MIDI note, chord intervals) per bar.
_MAJ7, _MIN7, _MAJ, _MIN, _DOM7 = [0, 4, 7, 11], [0, 3, 7, 10], [0, 4, 7], [0, 3, 7], [0, 4, 7, 10]

STYLES = {
    "calm":   dict(bpm=72,  prog=[(57, _MIN7), (53, _MAJ7), (48, _MAJ7), (55, _DOM7)], drums="none",  arp=False, pad=0.55, bright=0.4),
    "upbeat": dict(bpm=118, prog=[(60, _MAJ), (67, _MAJ), (57, _MIN), (65, _MAJ)],      drums="pop",   arp=True,  pad=0.35, bright=0.9),
    "lofi":   dict(bpm=82,  prog=[(62, _MIN7), (55, _DOM7), (60, _MAJ7), (57, _MIN7)],  drums="lofi",  arp=False, pad=0.45, bright=0.3),
    "epic":   dict(bpm=90,  prog=[(57, _MIN), (53, _MAJ), (48, _MAJ), (55, _MAJ)],      drums="epic",  arp=True,  pad=0.6,  bright=0.6),
}


def _freq(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def _tone(freq: float, n: int, bright: float, rng: np.random.Generator) -> np.ndarray:
    t = np.arange(n) / SR
    detune = 1 + rng.uniform(-0.002, 0.002)
    wave_ = np.sin(2 * np.pi * freq * t) + bright * 0.3 * np.sin(2 * np.pi * 2 * freq * detune * t)
    wave_ += bright * 0.12 * (2 / np.pi) * np.arcsin(np.sin(2 * np.pi * 3 * freq * t))  # soft triangle overtone
    return wave_


def _env(n: int, attack: float, release: float) -> np.ndarray:
    a, r = max(1, int(attack * SR)), max(1, int(release * SR))
    env = np.ones(n)
    env[:a] = np.linspace(0, 1, a)
    env[-r:] *= np.linspace(1, 0, r)
    return env


def _pluck(freq: float, n: int, decay: float) -> np.ndarray:
    t = np.arange(n) / SR
    return np.sin(2 * np.pi * freq * t) * np.exp(-t / decay) * _env(n, 0.005, 0.02)


def _kick(n: int) -> np.ndarray:
    t = np.arange(n) / SR
    f = 50 + 70 * np.exp(-t / 0.04)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.18)


def _noise_hit(n: int, decay: float, rng: np.random.Generator, smooth: int) -> np.ndarray:
    t = np.arange(n) / SR
    noise = rng.standard_normal(n)
    if smooth > 1:
        noise = np.convolve(noise, np.ones(smooth) / smooth, mode="same")
    return noise * np.exp(-t / decay)


def _add(buf: np.ndarray, sig: np.ndarray, start: int, gain: float) -> None:
    end = min(len(buf), start + len(sig))
    if start < end:
        buf[start:end] += gain * sig[: end - start]


def _render_cycle(style: dict, rng: np.random.Generator, variation: int) -> np.ndarray:
    beat = int(SR * 60 / style["bpm"])
    bar = beat * 4
    out = np.zeros(bar * len(style["prog"]))
    hat_smooth = 1 if style["drums"] == "pop" else 3

    for b, (root, chord) in enumerate(style["prog"]):
        s = b * bar
        # Pad: sustained chord with slow swell.
        pad = sum(_tone(_freq(root + iv), bar, style["bright"], rng) for iv in chord) / len(chord)
        _add(out, pad * _env(bar, 0.35, 0.4), s, style["pad"])
        # Bass: root an octave down on beats 1 and 3 (every beat for upbeat).
        step = 1 if style["drums"] == "pop" else 2
        for q in range(0, 4, step):
            _add(out, _pluck(_freq(root - 12), beat * step, 0.35), s + q * beat, 0.45)
        # Arpeggio / melody on 8th notes, varied on the second cycle.
        if style["arp"] or variation:
            pattern = [0, 1, 2, 1, 2, 3, 2, 1] if variation % 2 == 0 else [0, 2, 1, 3, 2, 1, 3, 2]
            eighth = beat // 2
            for k, idx in enumerate(pattern):
                iv = chord[idx % len(chord)] + 12
                _add(out, _pluck(_freq(root + iv), eighth, 0.18), s + k * eighth, 0.16 if style["arp"] else 0.08)
        # Drums.
        drums = style["drums"]
        if drums == "none":
            continue
        for q in range(4):
            pos = s + q * beat
            swing = int(beat * 0.08) if drums == "lofi" else 0
            if q in (0, 2) or (drums == "epic" and q == 3):
                _add(out, _kick(beat), pos, 0.9 if drums != "lofi" else 0.6)
            if q in (1, 3):
                _add(out, _noise_hit(beat, 0.09, rng, 4), pos, 0.35 if drums != "lofi" else 0.2)
            _add(out, _noise_hit(beat // 2, 0.025, rng, hat_smooth), pos, 0.08)
            _add(out, _noise_hit(beat // 2, 0.025, rng, hat_smooth), pos + beat // 2 + swing, 0.06)
    return out


def generate(mood: str, seconds: float, out_path: Path, seed: int = 0) -> Path:
    style = STYLES.get(mood, STYLES["calm"])
    rng = np.random.default_rng(seed)
    cycles = [_render_cycle(style, rng, v) for v in range(2)]
    n_total = int(seconds * SR) + SR
    parts, length, i = [], 0, 0
    while length < n_total:
        parts.append(cycles[i % 2])
        length += len(cycles[i % 2])
        i += 1
    mono = np.concatenate(parts)[:n_total]

    if style["drums"] == "lofi":  # warm, slightly muffled tone
        mono = np.convolve(mono, np.ones(6) / 6, mode="same")

    # Gentle stereo width via a few-ms delay on one channel.
    d = int(0.012 * SR)
    left, right = mono, np.concatenate([np.zeros(d), mono[:-d]])
    stereo = np.stack([left, right], axis=1)
    stereo *= _env(len(stereo), 2.0, 3.0)[:, None]
    peak = np.max(np.abs(stereo)) or 1.0
    pcm = (stereo / peak * 0.85 * 32767).astype("<i2")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return out_path
