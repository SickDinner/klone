"""Bounded descriptive measurements for explicitly supplied PCM music fixtures.

No speech recognition, identity or emotion inference, network access or writes.
"""
from __future__ import annotations

import argparse
import json
import math
import struct
import wave
from pathlib import Path

MAX_DURATION_SECONDS = 600
MAX_FRAMES = 96_000 * MAX_DURATION_SECONDS
CHUNK_FRAMES = 16_384


def analyze_music_wav(path: Path) -> dict:
    with wave.open(str(path), "rb") as source:
        channels = source.getnchannels()
        rate = source.getframerate()
        frames = source.getnframes()
        if (source.getsampwidth() != 2 or channels not in (1, 2)
                or not 8000 <= rate <= 96000 or not 0 < frames <= MAX_FRAMES
                or frames > rate * MAX_DURATION_SECONDS
                or source.getcomptype() != "NONE"):
            raise ValueError("Expected bounded mono/stereo 16-bit PCM WAV")
        totals = [0] * channels
        squares = [0] * channels
        peaks = [0] * channels
        zeros = [0] * channels
        full = [0] * channels
        remaining = frames
        while remaining:
            take = min(CHUNK_FRAMES, remaining)
            raw = source.readframes(take)
            if len(raw) != take * channels * 2:
                raise ValueError("Truncated PCM data")
            samples = struct.unpack("<" + "h" * (take * channels), raw)
            for channel in range(channels):
                values = samples[channel::channels]
                totals[channel] += sum(values)
                squares[channel] += sum(x * x for x in values)
                peaks[channel] = max(peaks[channel], max(abs(x) for x in values))
                zeros[channel] += values.count(0)
                full[channel] += values.count(-32768) + values.count(32767)
            remaining -= take
    results = []
    for channel in range(channels):
        results.append({
            "channel": channel,
            "peak": round(peaks[channel] / 32768, 8),
            "rms": round(math.sqrt(squares[channel] / frames) / 32768, 8),
            "mean": round(totals[channel] / frames / 32768, 8),
            "zero_fraction": round(zeros[channel] / frames, 8),
            "full_scale_fraction": round(full[channel] / frames, 8),
        })
    return {
        "schema": "klone.music_pcm_metrics.v1",
        "sample_rate_hz": rate,
        "frames": frames,
        "duration_seconds": round(frames / rate, 8),
        "channels": results,
        "limitations": ["descriptive PCM metrics only", "not perceptual loudness or musical quality"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    try:
        report = analyze_music_wav(args.path)
    except (ValueError, OSError, EOFError, wave.Error) as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
