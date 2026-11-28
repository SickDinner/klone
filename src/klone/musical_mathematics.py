"""Educational comparison of fixed musical interval ratios and 12-TET."""
from __future__ import annotations

import argparse
from fractions import Fraction
import json
import math

INTERVALS = (
    ("unison", 0, 1, 1),
    ("minor_third", 3, 6, 5),
    ("major_third", 4, 5, 4),
    ("perfect_fourth", 5, 4, 3),
    ("perfect_fifth", 7, 3, 2),
    ("minor_sixth", 8, 8, 5),
    ("major_sixth", 9, 5, 3),
    ("octave", 12, 2, 1),
)


def tuning_study():
    """Compare idealized ratios at a fixed A4 reference of 440 Hz."""
    rows = []
    for name, semitones, numerator, denominator in INTERVALS:
        ratio = Fraction(numerator, denominator)
        equal = 2 ** (semitones / 12)
        cents = 1200 * math.log2(float(ratio))
        rows.append({
            "interval": name,
            "semitones": semitones,
            "just_ratio": str(numerator) + "/" + str(denominator),
            "just_frequency_hz": 440 * float(ratio),
            "equal_frequency_hz": 440 * equal,
            "just_cents": cents,
            "equal_cents": 100 * semitones,
            "just_minus_equal_cents": cents - 100 * semitones,
        })
    comma = Fraction(3, 2) ** 12 / 2 ** 7
    return {
        "schema": "klone.musical_mathematics.v1",
        "reference_hz": 440,
        "intervals": rows,
        "pythagorean_comma": {
            "ratio": str(comma),
            "cents": 1200 * math.log2(float(comma)),
        },
        "limitations": [
            "Selected conventional just-intonation ratios, not a unique universal tuning.",
            "Ideal mathematical frequencies, not measurements of recorded audio.",
            "The cents difference is not a perceptual or aesthetic quality score.",
            "Pythagorean comma compares twelve pure fifths with seven octaves.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    print(json.dumps(tuning_study(), indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
