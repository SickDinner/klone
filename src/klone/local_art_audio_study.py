"""Offline descriptive study of explicitly selected local music WAV files.

No recording, network, voice identification, metadata inference or memory writes.
"""
from __future__ import annotations

import argparse
from array import array
import cmath
import hashlib
import io
import json
import math
from pathlib import Path
import stat
import sys
import wave

MAX_BYTES = 16 * 1024 * 1024
MAX_SECONDS = 60
FFT_SIZE = 1024
MAX_WINDOWS = 16


def _read_file(path):
    path = Path(path)
    if not stat.S_ISREG(path.stat().st_mode):
        raise ValueError("expected a regular local WAV file")
    with path.open("rb") as handle:
        data = handle.read(MAX_BYTES + 1)
    if not data or len(data) > MAX_BYTES:
        raise ValueError("WAV byte limit exceeded or empty input")
    return data


def _fft(samples):
    """Radix-two transform of a real, zero-padded rectangular window."""
    n = FFT_SIZE
    a = [complex(v) for v in samples]
    a.extend([0j] * (n - len(a)))
    j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j ^= bit
        if i < j:
            a[i], a[j] = a[j], a[i]
    size = 2
    while size <= n:
        root = cmath.exp(-2j * math.pi / size)
        for start in range(0, n, size):
            w = 1 + 0j
            for k in range(start, start + size // 2):
                u, v = a[k], a[k + size // 2] * w
                a[k], a[k + size // 2] = u + v, u - v
                w *= root
        size *= 2
    return [(z.real*z.real + z.imag*z.imag) *
            (1 if i in (0,n//2) else 2)
            for i,z in enumerate(a[:n//2+1])]


def analyze_audio(path):
    data = _read_file(path)
    with wave.open(io.BytesIO(data), "rb") as source:
        channels, width, rate, frames, compression, _ = source.getparams()
        if channels not in (1,2) or width != 2 or compression != "NONE":
            raise ValueError("expected mono or stereo signed 16-bit PCM")
        if not 8000 <= rate <= 48000 or not 0 < frames <= rate * MAX_SECONDS:
            raise ValueError("sample rate or duration outside supported bounds")
        raw = source.readframes(frames)
    if len(raw) != frames * channels * 2:
        raise ValueError("truncated PCM data")
    samples = array("h", raw)
    if sys.byteorder != "little":
        samples.byteswap()

    channel_metrics = []
    for channel in range(channels):
        values = samples[channel::channels]
        peak = max(abs(v) for v in values) / 32768
        rms = math.sqrt(sum(v*v for v in values)/frames) / 32768
        channel_metrics.append({
            "peak": peak, "rms": rms,
            "dc_mean": sum(values)/frames/32768,
            "full_scale_sample_count": sum(v in (-32768,32767) for v in values),
            "crest_factor": None if rms == 0 else peak/rms,
        })

    block = rate // 10
    envelope = []
    for start in range(0, frames, block):
        end = min(start + block, frames)
        chunk = samples[start*channels:end*channels]
        envelope.append(math.sqrt(sum(v*v for v in chunk)/len(chunk))/32768)

    last = max(0, frames-FFT_SIZE)
    windows = min(MAX_WINDOWS, max(1, frames//FFT_SIZE))
    starts = [0] if windows == 1 else [i*last//(windows-1) for i in range(windows)]
    power = [0.0] * (FFT_SIZE//2+1)
    for start in starts:
        end = min(start + FFT_SIZE, frames)
        for c in range(channels):
            p = _fft(samples[start*channels+c:end*channels:channels])
            for i,v in enumerate(p):
                power[i] += v
    total = math.fsum(power)
    frequencies = [i*rate/FFT_SIZE for i in range(len(power))]
    bands = [0.0] * 4
    for f,p in zip(frequencies,power):
        bands[0 if f < 200 else 1 if f < 1000 else 2 if f < 4000 else 3] += p
    centroid = None if total == 0 else math.fsum(f*p for f,p in zip(frequencies,power))/total
    return {
        "schema": "klone.local_art_audio_study.v1",
        "source": {"sha256": hashlib.sha256(data).hexdigest(),
                   "sample_rate_hz":rate, "channels":channels, "frames":frames,
                   "duration_seconds": frames/rate},
        "channel_metrics": channel_metrics,
        "envelope": {"nominal_block_ms":100,"rms":envelope},
        "sampled_spectrum": {
            "fft_size":FFT_SIZE, "window":"rectangular",
            "window_count":len(starts),
            "bin_spacing_hz":rate/FFT_SIZE,
            "power_centroid_hz":centroid,
            "band_labels":["0_to_200_exclusive","200_to_1000_exclusive",
                           "1000_to_4000_exclusive","4000_to_nyquist_inclusive"],
            "band_power_fractions":None if total == 0 else [p/total for p in bands],
        },
        "limitations":[
            "Explicit local mono/stereo 16-bit PCM WAV music; 8–48 kHz, 60 seconds and 16 MiB maximum.",
            "Peak and RMS use digital full scale, not sound pressure or perceived loudness.",
            "Full-scale sample count is not proof of clipping.",
            "Envelope uses approximately 100 ms blocks; final block may be shorter.",
            "Spectrum aggregates channel power across at most 16 sampled rectangular windows; not a full-file spectral measurement.",
            "Short windows zero-padded; spectral leakage and limited resolution apply.",
            "Undefined centroid and band fractions use null for zero sampled power.",
            "No tempo, pitch, musical quality, speaker identity or subjective preference inference.",
            "No microphone, network, personal inference, production integration or persistent memory write.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio", type=Path)
    args = parser.parse_args(argv)
    try:
        report = analyze_audio(args.audio)
    except (OSError, ValueError, EOFError, wave.Error) as exc:
        parser.exit(2, "Audio analysis failed: " + str(exc) + "\n")
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
