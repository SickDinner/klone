"""Educational mathematical art: fixed-view Mandelbrot escape-time illustrations."""
from __future__ import annotations

import argparse
from collections import Counter
import io
import json
from pathlib import Path

from PIL import Image

MAX_SIZE = 256
MAX_ITERATIONS = 96


def escape_count(real: float, imag: float, iterations: int) -> int | None:
    """Return first escape iteration, or None when no escape was observed."""
    z = 0j
    c = complex(real, imag)
    for step in range(1, iterations + 1):
        z = z * z + c
        if z.real * z.real + z.imag * z.imag > 4:
            return step
    return None


def fractal_study(size: int = 128, iterations: int = 48) -> tuple[dict, bytes]:
    if type(size) is not int or not 16 <= size <= MAX_SIZE:
        raise ValueError("Expected image size from 16 to 256")
    if type(iterations) is not int or not 1 <= iterations <= MAX_ITERATIONS:
        raise ValueError("Expected 1 to 96 iterations")
    counts = Counter()
    unresolved = 0
    pixels = []
    for y in range(size):
        imag = 1.5 - 3 * (y + 0.5) / size
        for x in range(size):
            real = -2.25 + 3 * (x + 0.5) / size
            count = escape_count(real, imag, iterations)
            if count is None:
                unresolved += 1
                pixels.append((15, 18, 30))
            else:
                counts[count] += 1
                pixels.append((32 + (count * 17) % 224,
                               32 + (count * 11) % 224,
                               48 + (count * 23) % 208))
    image = Image.new("RGB", (size, size))
    image.putdata(pixels)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return ({
        "schema": "klone.fractal_art.v1",
        "dimensions": [size, size],
        "iterations": iterations,
        "viewport": {"real": [-2.25, 0.75], "imaginary": [-1.5, 1.5]},
        "escaped_samples": sum(counts.values()),
        "unresolved_samples": unresolved,
        "unresolved_fraction": unresolved / (size * size),
        "escape_histogram": {str(k): v for k, v in sorted(counts.items())},
        "limitations": [
            "Pixel-center samples in a fixed mathematical viewport.",
            "Unresolved after a finite iteration limit is not proof of membership.",
            "Arbitrary illustrative RGB coloring; no aesthetic inference.",
            "Floating-point computation, not a rigorous interval-arithmetic proof.",
        ],
    }, output.getvalue())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", type=int, default=128)
    parser.add_argument("--iterations", type=int, default=48)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        report, png = fractal_study(args.size, args.iterations)
        if args.output is not None:
            with args.output.open("xb") as output:
                output.write(png)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
