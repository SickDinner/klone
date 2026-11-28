"""Bounded mathematical artwork from elementary one-dimensional cellular automata."""
from __future__ import annotations

import argparse
import io
import json
import math
from pathlib import Path

from PIL import Image


def cellular_study(rule: int = 30, width: int = 145,
                   generations: int = 72) -> tuple[dict, bytes]:
    """Single central seed, periodic boundaries, binary raster artwork."""
    if type(rule) is not int or not 0 <= rule <= 255:
        raise ValueError("Expected an integer rule from 0 to 255")
    if type(width) is not int or not 3 <= width <= 257:
        raise ValueError("Expected width from 3 to 257")
    if type(generations) is not int or not 1 <= generations <= 128:
        raise ValueError("Expected 1 to 128 generations")
    row = [0] * width
    row[width // 2] = 1
    pixels = []
    active_counts = []
    for _ in range(generations):
        active_counts.append(sum(row))
        pixels.extend((234, 184, 86) if v else (21, 35, 54) for v in row)
        row = [(rule >> (4 * row[(i - 1) % width] + 2 * row[i]
                         + row[(i + 1) % width])) & 1 for i in range(width)]
    active = sum(active_counts)
    total = width * generations
    fraction = active / total
    entropy = -sum(p * math.log2(p) for p in (fraction, 1 - fraction) if p)
    image = Image.new("RGB", (width, generations))
    image.putdata(pixels)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return ({
        "schema": "klone.cellular_art.v1",
        "rule": rule,
        "dimensions": [width, generations],
        "seed": "single_center_cell",
        "boundary": "periodic",
        "active_counts_per_row": active_counts,
        "active_samples": active,
        "total_samples": total,
        "active_fraction": fraction,
        "binary_marginal_entropy_bits": entropy,
        "limitations": [
            "Synthetic binary artwork with a fixed single-cell initial condition.",
            "The first image row is the initial condition, not an evolved generation.",
            "Periodic boundaries can alter patterns when they meet the edges.",
            "Binary marginal entropy measures state proportions, not spatial complexity or randomness.",
            "No inference of consciousness, aesthetic merit or physical processes.",
        ],
    }, output.getvalue())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rule", type=int, default=30)
    parser.add_argument("--width", type=int, default=145)
    parser.add_argument("--generations", type=int, default=72)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        report, png = cellular_study(args.rule, args.width, args.generations)
        if args.output is not None:
            with args.output.open("xb") as output:
                output.write(png)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
