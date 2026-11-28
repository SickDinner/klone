"""Fixed educational sRGB and CIELAB(D65) comparison.

Formula references: https://www.oceanopticsbook.info/view/photometry-and-visibility/from-xyz-to-rgb
and https://en.wikipedia.org/wiki/CIELAB_color_space (XYZ conversion).
"""
from __future__ import annotations

import argparse
import json
import math

MATRIX = (
    (0.4124564, 0.3575761, 0.1804375),
    (0.2126729, 0.7151522, 0.0721750),
    (0.0193339, 0.1191920, 0.9503041),
)
WHITE = (0.95047, 1.0, 1.08883)
PAIRS = (
    ("dark_gray", (32, 32, 32), (64, 64, 64)),
    ("light_gray", (223, 223, 223), (255, 255, 255)),
    ("red_change", (128, 128, 128), (160, 128, 128)),
    ("green_change", (128, 128, 128), (128, 160, 128)),
    ("blue_change", (128, 128, 128), (128, 128, 160)),
)


def _linear(channel):
    v = channel / 255
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def _lab(rgb):
    linear = tuple(_linear(c) for c in rgb)
    xyz = [sum(a * b for a, b in zip(row, linear)) for row in MATRIX]
    delta = 6 / 29

    def f(t):
        return t ** (1 / 3) if t > delta ** 3 else t / (3 * delta ** 2) + 4 / 29

    x, y, z = (f(v / w) for v, w in zip(xyz, WHITE))
    return (116 * y - 16, 500 * (x - y), 200 * (y - z))


def color_study():
    observations = []
    for name, first, second in PAIRS:
        a, b = _lab(first), _lab(second)
        observations.append({
            "example": name,
            "first_srgb8": list(first),
            "second_srgb8": list(second),
            "first_lab_d65": list(a),
            "second_lab_d65": list(b),
            "encoded_rgb_distance": math.dist(first, second),
            "delta_e_76": math.dist(a, b),
        })
    return {
        "schema": "klone.perceptual_color_study.v1",
        "reference_white_xyz": list(WHITE),
        "observations": observations,
        "limitations": [
            "Five fixed synthetic 8-bit sRGB pairs; no external image input.",
            "CIELAB uses D65 white, not the D50 white used by CSS Lab.",
            "Delta E 76 is an approximate color difference model, not a human observation.",
            "RGB and Lab distances have different units and cannot be directly subtracted.",
            "No display calibration, observer experiment or artistic quality claim.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    print(json.dumps(color_study(), indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
