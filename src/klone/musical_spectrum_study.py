"""Fixed synthetic musical harmonic spectra and descriptive timbre features.

All amplitudes are relative mathematical peak amplitudes, not SPL.
No audio recording, playback, calibration or listening experiment.
"""
from __future__ import annotations

import argparse
import json
import math

FIXTURES = (
    ("pure_tone", 220, (1.0,)),
    ("octave_tone", 440, (1.0,)),
    ("two_equal_harmonics", 220, (1.0, 1.0)),
    ("soft_harmonics", 220, (1.0, .5, .25, .125)),
    ("bright_harmonics", 220, (1.0, 1.0, 1.0, 1.0)),
    ("odd_harmonics", 220, (1.0, 0.0, 1/3, 0.0, 1/5)),
    ("soft_octave", 440, (1.0, .5, .25, .125)),
    ("quiet_soft", 220, (.25, .125, .0625, .03125)),
    ("silence", 220, (0.0, 0.0, 0.0, 0.0)),
)


def mel_coordinate(hz):
    """Conventional logarithmic mel-scale approximation; not listener data."""
    if not math.isfinite(hz) or hz < 0:
        raise ValueError("frequency must be finite and nonnegative")
    return 2595 * math.log10(1 + hz/700)


def spectrum_metrics(fundamental, amplitudes):
    """Describe a bounded synthetic harmonic spectrum using relative powers."""
    if (not math.isfinite(fundamental) or not 0 < fundamental <= 1000
            or not 1 <= len(amplitudes) <= 16
            or any(not math.isfinite(a) or not 0 <= a <= 1 for a in amplitudes)):
        raise ValueError("expected bounded synthetic musical spectrum")
    frequencies = [fundamental*i for i in range(1,len(amplitudes)+1)]
    power = [a*a for a in amplitudes]
    total = math.fsum(power)
    result = {
        "fundamental_grid_hz": fundamental,
        "harmonic_frequencies_hz": frequencies,
        "relative_peak_amplitudes": list(amplitudes),
        "total_relative_power": total,
        "ideal_cycle_rms": math.sqrt(total/2),
        "active_harmonic_count": sum(a>0 for a in power),
        "normalized_harmonic_power": None,
        "power_centroid_hz": None,
        "power_spread_hz": None,
        "power_centroid_mel": None,
        "harmonic_power_entropy_bits": None,
        "power_rolloff_85_hz": None,
        "fundamental_power_fraction": None,
    }
    if not total:
        return result
    weights = [p/total for p in power]
    center = math.fsum(f*w for f,w in zip(frequencies,weights))
    rolloff = next(f for i,f in enumerate(frequencies)
                   if math.fsum(power[:i+1]) >= .85*total)
    result.update({
        "normalized_harmonic_power": weights,
        "power_centroid_hz": center,
        "power_spread_hz": math.sqrt(math.fsum(w*(f-center)**2
                                              for f,w in zip(frequencies,weights))),
        "power_centroid_mel": math.fsum(mel_coordinate(f)*w
                                        for f,w in zip(frequencies,weights)),
        "harmonic_power_entropy_bits": -math.fsum(w*math.log2(w) for w in weights if w),
        "power_rolloff_85_hz": rolloff,
        "fundamental_power_fraction": weights[0],
    })
    return result


def spectrum_study():
    return {
        "schema": "klone.musical_spectrum_study.v1",
        "observations": [{"example": name, "metrics": spectrum_metrics(f,a)}
                         for name,f,a in FIXTURES],
        "limitations": [
            "Nine fixed synthetic harmonic spectra; no external audio or playback.",
            "Power is squared relative amplitude, not calibrated physical sound power.",
            "Ideal cycle RMS assumes distinct integer harmonics averaged over a full cycle.",
            "Mel coordinates are an approximate frequency mapping, not loudness or hearing tests.",
            "Centroid, spread and entropy describe spectral structure, not perceived timbre quality.",
            "Normalized metrics undefined for silence; represented by null.",
            "No pitch estimator, production integration or consciousness claim.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    print(json.dumps(spectrum_study(), indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
