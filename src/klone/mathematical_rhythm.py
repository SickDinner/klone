"""Mathematical music and geometry: bounded circular pulse patterns."""
from __future__ import annotations

import argparse
import json
import math


def rhythm_study(steps: int, pulses: int) -> dict:
    """Distribute pulses by a floor-difference rule on a circular step grid."""
    if type(steps) is not int or not 1 <= steps <= 72:
        raise ValueError("Expected 1 to 72 steps")
    if type(pulses) is not int or not 0 <= pulses <= steps:
        raise ValueError("Expected 0 to steps pulses")
    pattern = [
        ((i + 1) * pulses) // steps - (i * pulses) // steps
        for i in range(steps)
    ]
    positions = [i for i, value in enumerate(pattern) if value]
    gaps = [
        (positions[(i + 1) % pulses] - pos) % steps or steps
        for i, pos in enumerate(positions)
    ]
    period = next(k for k in range(1, steps + 1)
                  if steps % k == 0
                  and all(pattern[i] == pattern[i % k] for i in range(steps)))
    return {
        "schema": "klone.mathematical_rhythm.v1",
        "steps": steps,
        "pulses": pulses,
        "pattern": pattern,
        "pulse_positions_zero_based": positions,
        "cyclic_gaps_steps": gaps,
        "density": pulses / steps,
        "fundamental_period_steps": period,
        "rotational_repetitions": steps // period,
        "limitations": [
            "A floor-difference pulse distribution, not a claim of a unique canonical Euclidean rhythm.",
            "Equal time steps; no tempo, expressive timing, accent or musical quality inference.",
            "No audio generated or source audio analyzed.",
        ],
    }


def render_rhythm_svg(steps: int, pulses: int) -> str:
    report = rhythm_study(steps, pulses)
    markers = []
    for i, active in enumerate(report["pattern"]):
        angle = 2 * math.pi * i / steps - math.pi / 2
        x, y = 150 + 112 * math.cos(angle), 150 + 112 * math.sin(angle)
        radius = 4 if steps > 36 else 6
        color = "#f6c76b" if active else "#65758a"
        markers.append(
            f"<circle cx='{x:.4f}' cy='{y:.4f}' r='{radius}' fill='{color}'/>"
        )
    return (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 300 300' "
        "role='img' aria-labelledby='title'>"
        f"<title id='title'>Circular rhythm: {pulses} pulses in {steps} steps</title>"
        "<rect width='300' height='300' rx='12' fill='#182333'/>"
        "<circle cx='150' cy='150' r='112' stroke='#65758a' fill='none'/>"
        + "".join(markers)
        + f"<text x='150' y='155' fill='white' font-size='22' "
          f"text-anchor='middle'>{pulses}/{steps}</text></svg>"
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--steps", type=int, default=72)
    parser.add_argument("--pulses", type=int, default=8)
    parser.add_argument("--format", choices=("json", "svg"), default="json")
    args = parser.parse_args(argv)
    try:
        result = rhythm_study(args.steps, args.pulses)
    except ValueError as exc:
        parser.error(str(exc))
    print(render_rhythm_svg(args.steps, args.pulses) if args.format == "svg"
          else json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
