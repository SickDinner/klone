"""Bounded music-clip spectral measurements, no recognition or classification."""
from __future__ import annotations

import cmath
import math
import struct
import wave
from pathlib import Path

WINDOW = 1024
MAX_WINDOWS = 32
BANDS = ((0, 250), (250, 500), (500, 2000), (2000, 4000), (4000, 96000))


def _fft(values):
    n = len(values)
    if n == 1:
        return [complex(values[0])]
    even = _fft(values[::2])
    odd = _fft(values[1::2])
    rotated = [cmath.exp(-2j * math.pi * k / n) * odd[k] for k in range(n // 2)]
    return [even[k] + rotated[k] for k in range(n // 2)] + [
        even[k] - rotated[k] for k in range(n // 2)]


def music_clip_spectrum(path: Path) -> dict:
    """Measure first complete Hann windows of a mono/stereo 16-bit music clip."""
    with wave.open(str(path), "rb") as source:
        channels, rate = source.getnchannels(), source.getframerate()
        frames = source.getnframes()
        if channels not in (1, 2) or source.getsampwidth() != 2 or not 8000 <= rate <= 96000:
            raise ValueError("Expected mono/stereo 16-bit PCM WAV")
        if frames < WINDOW or source.getcomptype() != "NONE":
            raise ValueError("Expected at least one full PCM window")
        windows = min(frames // WINDOW, MAX_WINDOWS)
        weights = [0.5 - 0.5 * math.cos(2 * math.pi * i / WINDOW) for i in range(WINDOW)]
        powers = [[0.0] * (WINDOW // 2 + 1) for _ in range(channels)]
        for _ in range(windows):
            raw = source.readframes(WINDOW)
            if len(raw) != WINDOW * channels * 2:
                raise ValueError("Truncated PCM window")
            samples = struct.unpack("<" + "h" * (WINDOW * channels), raw)
            for channel in range(channels):
                values = samples[channel::channels]
                mean = sum(values) / WINDOW
                transformed = _fft([(x - mean) * w for x, w in zip(values, weights)])
                for k in range(WINDOW // 2 + 1):
                    factor = 1 if k in (0, WINDOW // 2) else 2
                    powers[channel][k] += factor * abs(transformed[k]) ** 2
    reports = []
    for channel, power in enumerate(powers):
        total = sum(power)
        band_power = [sum(p for k, p in enumerate(power)
                          if low <= k * rate / WINDOW < high)
                      for low, high in BANDS]
        reports.append({
            "channel": channel,
            "band_fractions": [
                {"low_hz": low, "high_hz_exclusive": high,
                 "fraction": round(value / total, 8) if total else None}
                for (low, high), value in zip(BANDS, band_power)
            ],
            "spectral_centroid_hz": round(sum(k * rate / WINDOW * p for k, p in enumerate(power)) / total, 6)
            if total else None,
        })
    return {
        "schema": "klone.music_clip_spectrum.v1",
        "sample_rate_hz": rate,
        "window_frames": WINDOW,
        "windows": windows,
        "analyzed_frames": windows * WINDOW,
        "source_declared_frames": frames,
        "channels": reports,
        "limitations": [
            "Leading complete windows only, not full-track analysis or file validation.",
            "Per-window mean removed; periodic Hann weighting; one-sided power fractions.",
            "Frequency resolution depends on sample rate; no pitch, tempo or loudness inference.",
        ],
    }
