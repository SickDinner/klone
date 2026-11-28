"""Fixed mathematical illustrations of the three regular Euclidean tilings."""
from __future__ import annotations

import argparse
import json
import math

SIDES = {"triangle": 3, "square": 4, "hexagon": 6}


def tessellation_study(kind: str = "hexagon") -> dict:
    if not isinstance(kind, str) or kind not in SIDES:
        raise ValueError("Expected triangle, square or hexagon")
    n = SIDES[kind]
    angle = 180 * (n - 2) / n
    area = n / (4 * math.tan(math.pi / n))
    return {
        "schema": "klone.tessellation_art.v1",
        "kind": kind,
        "sides_per_tile": n,
        "unit_side_length": 1,
        "interior_angle_degrees": angle,
        "tiles_per_vertex": int(round(360 / angle)),
        "unit_tile_area": area,
        "unit_tile_perimeter": n,
        "limitations": [
            "Ideal regular polygons in an infinite Euclidean plane.",
            "SVG is a finite clipped illustration, not a computational coverage proof.",
            "Unit-side measurements are mathematical, not physical measurements.",
            "No claim of aesthetic optimality.",
        ],
    }


def render_tessellation_svg(kind: str = "hexagon") -> str:
    report = tessellation_study(kind)
    n = report["sides_per_tile"]
    colors = ("#82e5d8", "#eab856", "#7197b8")
    polygons = []
    side = 32
    height = math.sqrt(3) * side / 2

    def add(points, index):
        coords = " ".join(f"{x:.6f},{y:.6f}" for x, y in points)
        polygons.append(
            f"<polygon points='{coords}' fill='{colors[index % 3]}' "
            "stroke='#152336' stroke-width='0.6'/>"
        )

    if n == 3:
        for row in range(-1, 13):
            for col in range(-7, 14):
                x = (col + row / 2) * side
                y = row * height
                add(((x, y), (x + side, y), (x + side / 2, y + height)), col - row)
                add(((x + side, y), (x + 1.5 * side, y + height),
                     (x + side / 2, y + height)), col - row + 1)
    elif n == 4:
        for row in range(12):
            for col in range(12):
                x, y = col * side, row * side
                add(((x, y), (x + side, y), (x + side, y + side),
                     (x, y + side)), col + row)
    else:
        for col in range(-1, 10):
            for row in range(-1, 9):
                cx = col * 1.5 * side
                cy = (row + (col % 2) / 2) * 2 * height
                add([(cx + side * math.cos(i * math.pi / 3),
                      cy + side * math.sin(i * math.pi / 3))
                     for i in range(6)], col + 2 * row)
    return (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 360 360' "
        "role='img' aria-labelledby='title' overflow='hidden'>"
        f"<title id='title'>Regular {kind} tessellation</title>"
        "<rect width='360' height='360' fill='#152336'/>"
        + "".join(polygons) + "</svg>"
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=tuple(SIDES), default="hexagon")
    parser.add_argument("--format", choices=("json", "svg"), default="json")
    args = parser.parse_args(argv)
    print(render_tessellation_svg(args.kind) if args.format == "svg"
          else json.dumps(tessellation_study(args.kind), indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
