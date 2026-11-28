"""Bounded mathematical illustrations inspired by botanical phyllotaxis."""
from __future__ import annotations

import argparse
import json
import math

GOLDEN_RATIO = (1 + math.sqrt(5)) / 2
GOLDEN_ANGLE = 360 / (GOLDEN_RATIO ** 2)


def fibonacci_sequence(count: int) -> list[int]:
    if type(count) is not int or not 1 <= count <= 32:
        raise ValueError("Expected 1 to 32 Fibonacci terms")
    a, b = 0, 1
    result = []
    for _ in range(count):
        result.append(a)
        a, b = b, a + b
    return result


def phyllotaxis_study(count: int = 144) -> dict:
    """Generate an idealized golden-angle disk, not a biological simulation."""
    if type(count) is not int or not 1 <= count <= 512:
        raise ValueError("Expected 1 to 512 points")
    angle = math.radians(GOLDEN_ANGLE)
    denominator = max(1, count - 1)
    points = []
    for n in range(count):
        radius = math.sqrt(n / denominator)
        points.append({
            "index": n,
            "radius": round(radius, 10),
            "x": round(radius * math.cos(n * angle), 10),
            "y": round(radius * math.sin(n * angle), 10),
        })
    return {
        "schema": "klone.nature_mathematics.v1",
        "point_count": count,
        "golden_ratio": GOLDEN_RATIO,
        "golden_angle_degrees": GOLDEN_ANGLE,
        "fibonacci_terms": fibonacci_sequence(16),
        "points": points,
        "limitations": [
            "Idealized mathematical disk with golden-angle spacing.",
            "Radius follows square-root index spacing, not a measured growth process.",
            "Coordinates are rounded floating-point approximations.",
            "No claim that all plants follow this pattern or that it is aesthetically optimal.",
        ],
    }


def render_phyllotaxis_svg(count: int = 144) -> str:
    report = phyllotaxis_study(count)
    radius = max(1.4, min(4.5, 66 / math.sqrt(count)))
    circles = "".join(
        f"<circle cx='{180 + 152 * p['x']:.5f}' "
        f"cy='{180 - 152 * p['y']:.5f}' r='{radius:.3f}' "
        f"fill='{'#eab856' if p['index'] % 2 else '#82e5d8'}'/>"
        for p in report["points"]
    )
    return (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 360 360' "
        "role='img' aria-labelledby='title'>"
        f"<title id='title'>Golden-angle mathematical artwork, {count} points</title>"
        "<rect width='360' height='360' fill='#152336'/>"
        + circles + "</svg>"
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=144)
    parser.add_argument("--format", choices=("json", "svg"), default="json")
    args = parser.parse_args(argv)
    try:
        report = phyllotaxis_study(args.count)
    except ValueError as exc:
        parser.error(str(exc))
    print(render_phyllotaxis_svg(args.count) if args.format == "svg"
          else json.dumps(report, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
