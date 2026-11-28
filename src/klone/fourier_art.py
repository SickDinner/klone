"""Educational Fourier art from a fixed, ideal periodic square wave."""
from __future__ import annotations

import argparse
import json
import math


SAMPLES = 720


def fourier_study(terms: int = 9) -> dict:
    """Approximate sign(sin(t)) with its first odd sine harmonics."""
    if type(terms) is not int or not 1 <= terms <= 32:
        raise ValueError("Expected 1 to 32 odd harmonics")
    harmonics = [
        {"order": n, "amplitude": 4 / (math.pi * n)}
        for n in range(1, 2 * terms, 2)
    ]
    points = [
        [i / SAMPLES, round(math.fsum(
            h["amplitude"] * math.sin(h["order"] * 2 * math.pi * i / SAMPLES)
            for h in harmonics
        ), 10)]
        for i in range(SAMPLES + 1)
    ]
    # Parseval's identity: the target has mean square 1.
    captured = math.fsum(h["amplitude"] ** 2 / 2 for h in harmonics)
    return {
        "schema": "klone.fourier_art.v1",
        "target": "ideal_unit_square_wave",
        "terms": terms,
        "harmonics": harmonics,
        "points": points,
        "captured_mean_square": captured,
        "theoretical_residual_mean_square": max(0.0, 1 - captured),
        "sampled_peak_absolute": max(abs(y) for _, y in points),
        "limitations": [
            "Fixed mathematical square wave, not an analysis of recorded audio.",
            "Residual uses continuous-period Parseval identity, not sampled error.",
            "Sampled peak can underestimate the continuous peak.",
            "Finite sums exhibit ringing near discontinuities; no aesthetic inference.",
        ],
    }


def render_fourier_svg(terms: int = 9) -> str:
    report = fourier_study(terms)
    points = " ".join(f"{24 + 352*x:.5f},{120 - 75*y:.5f}"
                      for x, y in report["points"])
    return (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 400 240' "
        "role='img' aria-labelledby='title'>"
        f"<title id='title'>Square wave Fourier approximation, {terms} odd harmonics</title>"
        "<rect width='400' height='240' fill='#152336'/>"
        "<path d='M24 45 H200 M200 195 H376' stroke='#eab856' "
        "stroke-dasharray='5 4' fill='none'/>"
        "<path d='M24 120 H376' stroke='#65758a' fill='none'/>"
        f"<polyline points='{points}' fill='none' stroke='#82e5d8' stroke-width='1.5'/>"
        "</svg>"
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--terms", type=int, default=9)
    parser.add_argument("--format", choices=("json", "svg"), default="json")
    args = parser.parse_args(argv)
    try:
        report = fourier_study(args.terms)
    except ValueError as exc:
        parser.error(str(exc))
    print(render_fourier_svg(args.terms) if args.format == "svg"
          else json.dumps(report, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
