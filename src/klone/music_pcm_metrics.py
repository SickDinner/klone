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
        # Full one-second windows, independent of the IO chunk size.
        window_squares = [0] * channels
        window_energy = [[] for _ in range(channels)]
        window_frames = 0
        remaining = frames
        while remaining:
            take = min(CHUNK_FRAMES, remaining, rate - window_frames)
            raw = source.readframes(take)
            if len(raw) != take * channels * 2:
                raise ValueError("Truncated PCM data")
            samples = struct.unpack("<" + "h" * (take * channels), raw)
            for channel in range(channels):
                values = samples[channel::channels]
                totals[channel] += sum(values)
                energy = sum(x * x for x in values)
                squares[channel] += energy
                window_squares[channel] += energy
                peaks[channel] = max(peaks[channel], max(abs(x) for x in values))
                zeros[channel] += values.count(0)
                full[channel] += values.count(-32768) + values.count(32767)
            remaining -= take
            window_frames += take
            if window_frames == rate:
                for channel in range(channels):
                    window_energy[channel].append(window_squares[channel])
                window_squares = [0] * channels
                window_frames = 0
    results = []
    for channel in range(channels):
        energies = sorted(window_energy[channel])
        count = len(energies)

        def rms_value(energy):
            return round(math.sqrt(energy / rate) / 32768, 8)

        def percentile(fraction):
            if not count:
                return None
            return rms_value(energies[max(0, math.ceil(fraction * count) - 1)])

        crest_db = (round(20 * math.log10(peaks[channel] /
                    math.sqrt(squares[channel] / frames)), 8)
                    if squares[channel] else None)
        results.append({
            "channel": channel,
            "crest_factor_db": crest_db,
            "one_second_rms": {
                "full_window_count": count,
                "excluded_tail_frames": frames % rate,
                "minimum": rms_value(energies[0]) if count else None,
                "maximum": rms_value(energies[-1]) if count else None,
                "p10": percentile(0.10),
                "p90": percentile(0.90),
            },
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
        "limitations": ["descriptive PCM metrics only", "not perceptual loudness or musical quality",
                        "RMS percentiles use full one-second windows and nearest rank; tail excluded",
                        "Crest factor is sample peak divided by whole-file RMS; undefined for silence"],
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
