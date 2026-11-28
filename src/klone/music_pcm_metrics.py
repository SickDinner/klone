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

MAX_FRAMES = 480_000


def analyze_music_wav(path: Path) -> dict:
    with wave.open(str(path), "rb") as source:
        channels = source.getnchannels()
        rate = source.getframerate()
        frames = source.getnframes()
        if (source.getsampwidth() != 2 or channels not in (1, 2)
                or not 8000 <= rate <= 96000 or not 0 < frames <= MAX_FRAMES
                or source.getcomptype() != "NONE"):
            raise ValueError("Expected bounded mono/stereo 16-bit PCM WAV")
        raw = source.readframes(frames)
    if len(raw) != frames * channels * 2:
        raise ValueError("Truncated PCM data")
    samples = [item[0] for item in struct.iter_unpack("<h", raw)]
    results = []
    for channel in range(channels):
        values = samples[channel::channels]
        squares = sum(x * x for x in values)
        peak = max(abs(x) for x in values) / 32768
        rms = math.sqrt(squares / frames) / 32768
        results.append({
            "channel": channel,
            "peak": round(peak, 8),
            "rms": round(rms, 8),
            "mean": round(sum(values) / frames / 32768, 8),
            "zero_fraction": round(values.count(0) / frames, 8),
            "full_scale_fraction": round(sum(x in (-32768, 32767) for x in values) / frames, 8),
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
