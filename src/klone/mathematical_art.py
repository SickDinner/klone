"""Mathematical art teaching examples: regular polygons and rotational symmetry."""
from __future__ import annotations

import argparse
import json
import math


def polygon_study(sides: int) -> dict:
    if type(sides) is not int or not 3 <= sides <= 72:
        raise ValueError("Expected 3 to 72 sides")
    vertices = [
        (round(math.cos(2 * math.pi * k / sides), 10),
         round(math.sin(2 * math.pi * k / sides), 10))
        for k in range(sides)
    ]
    return {
        "schema": "klone.regular_polygon_study.v1",
        "sides": sides,
        "circumradius": 1,
        "rotation_order": sides,
        "reflection_axes": sides,
        "central_angle_degrees": 360 / sides,
        "interior_angle_degrees": 180 - 360 / sides,
        "area": sides * math.sin(2 * math.pi / sides) / 2,
        "perimeter": 2 * sides * math.sin(math.pi / sides),
        "vertices": [list(point) for point in vertices],
        "limitations": [
            "Ideal mathematical regular polygon of unit circumradius.",
            "Coordinates rounded for presentation; area and perimeter use floating point.",
            "Symmetry counts are theoretical, not image recognition or aesthetic evaluation.",
        ],
    }


def render_polygon(sides: int) -> str:
    report = polygon_study(sides)
    points = " ".join(f"{x * 90 + 110:.6f},{110 - y * 90:.6f}"
                      for x, y in report["vertices"])
    return (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 220 220' "
        "role='img' aria-labelledby='title'>"
        f"<title id='title'>Regular polygon with {sides} sides</title>"
        "<rect width='220' height='220' fill='#182333'/>"
        "<circle cx='110' cy='110' r='90' fill='none' stroke='#73829a'/>"
        f"<polygon points='{points}' fill='#236c78' fill-opacity='.35' "
        "stroke='#9ae5dc' stroke-width='1.5'/>"
        "</svg>"
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sides", type=int, default=72)
    parser.add_argument("--format", choices=("json", "svg"), default="json")
    args = parser.parse_args(argv)
    try:
        report = polygon_study(args.sides)
    except ValueError as exc:
        parser.error(str(exc))
    print(render_polygon(args.sides) if args.format == "svg" else
          json.dumps(report, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
