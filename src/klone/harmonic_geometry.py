"""Educational Lissajous illustrations for integer musical frequency ratios."""
from __future__ import annotations

import argparse
import json
import math


def harmonic_study(x_ratio: int, y_ratio: int, phase_quarters: int = 1) -> dict:
    if any(type(n) is not int or not 1 <= n <= 12 for n in (x_ratio, y_ratio)):
        raise ValueError("Expected integer ratios from 1 to 12")
    if type(phase_quarters) is not int or not 0 <= phase_quarters <= 3:
        raise ValueError("Expected phase quarters from 0 to 3")
    divisor = math.gcd(x_ratio, y_ratio)
    a, b = x_ratio // divisor, y_ratio // divisor
    phase = phase_quarters * math.pi / 2
    return {
        "schema": "klone.harmonic_geometry.v1",
        "input_ratio_xy": [x_ratio, y_ratio],
        "reduced_ratio_xy": [a, b],
        "phase_degrees": phase_quarters * 90,
        "interval_y_over_x_cents": round(1200 * math.log2(b / a), 8),
        "x_oscillations_per_common_period": a,
        "y_oscillations_per_common_period": b,
        "points": [
            [round(math.sin(2 * math.pi * a * i / 720 + phase), 10),
             round(math.sin(2 * math.pi * b * i / 720), 10)]
            for i in range(721)
        ],
        "limitations": [
            "Ideal sinusoidal parametric curves, not measured acoustic signals.",
            "Integer ratios are reduced before tracing a common period.",
            "Finite sampled points approximate the continuous curve.",
            "No claim of consonance preference, aesthetic merit or physical color-sound equivalence.",
        ],
    }


def render_harmonic_svg(x_ratio: int, y_ratio: int, phase_quarters: int = 1) -> str:
    report = harmonic_study(x_ratio, y_ratio, phase_quarters)
    points = " ".join(f"{150 + 125 * x:.5f},{150 - 125 * y:.5f}"
                      for x, y in report["points"])
    a, b = report["reduced_ratio_xy"]
    return (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 300 300' "
        "role='img' aria-labelledby='title'>"
        f"<title id='title'>Lissajous curve, x to y ratio {a}:{b}, "
        f"phase {report['phase_degrees']} degrees</title>"
        "<rect width='300' height='300' fill='#182333'/>"
        "<path d='M25 150 H275 M150 25 V275' stroke='#65758a' fill='none'/>"
        f"<polyline points='{points}' stroke='#8be3d9' stroke-width='1.5' fill='none'/>"
        "</svg>"
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--x-ratio", type=int, default=2)
    parser.add_argument("--y-ratio", type=int, default=3)
    parser.add_argument("--phase-quarters", type=int, default=1)
    parser.add_argument("--format", choices=("json", "svg"), default="json")
    args = parser.parse_args(argv)
    try:
        report = harmonic_study(args.x_ratio, args.y_ratio, args.phase_quarters)
    except ValueError as exc:
        parser.error(str(exc))
    print(render_harmonic_svg(args.x_ratio, args.y_ratio, args.phase_quarters)
          if args.format == "svg" else json.dumps(report, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
