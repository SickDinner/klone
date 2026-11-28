"""Local, still-image art study with bounded input and descriptive color statistics.

No network, camera, object recognition, identity analysis, or persistent memory.
Only explicitly selected PNG/JPEG artwork files are accepted.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import io
import json
import math
from pathlib import Path
import stat

from PIL import Image, ImageOps

MAX_BYTES = 16 * 1024 * 1024
MAX_PIXELS = 4_000_000
ANALYSIS_SIDE = 256


def _read_image(path):
    path = Path(path)
    if not stat.S_ISREG(path.stat().st_mode):
        raise ValueError("expected a regular local image file")
    with path.open("rb") as handle:
        data = handle.read(MAX_BYTES + 1)
    if not data or len(data) > MAX_BYTES:
        raise ValueError("image byte limit exceeded or empty input")
    return data


def _linear(v):
    v = v / 255
    return v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4


LINEAR = tuple(_linear(v) for v in range(256))


def _luminance(pixel):
    r, g, b = pixel
    return .2126 * LINEAR[r] + .7152 * LINEAR[g] + .0722 * LINEAR[b]


def analyze_image(path):
    data = _read_image(path)
    with Image.open(io.BytesIO(data), formats=["PNG", "JPEG"]) as source:
        if source.width * source.height > MAX_PIXELS:
            raise ValueError("image pixel limit exceeded")
        if getattr(source, "n_frames", 1) != 1:
            raise ValueError("animated images are not supported")
        image_format = source.format
        oriented = ImageOps.exif_transpose(source)
        original_size = list(oriented.size)
        # Explicit white matte for transparency, without exporting metadata.
        rgba = oriented.convert("RGBA")
        white = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        rgb = Image.alpha_composite(white, rgba).convert("RGB")
        rgb.thumbnail((ANALYSIS_SIDE, ANALYSIS_SIDE), Image.Resampling.BOX)
    pixels = list(rgb.getdata())
    width, height = rgb.size
    count = len(pixels)
    luminance = [_luminance(p) for p in pixels]
    mean = math.fsum(luminance) / count
    variance = math.fsum((v - mean) ** 2 for v in luminance) / count

    # Fixed 4-bit/channel RGB bins. Representative color is bin midpoint.
    bins = Counter((r // 16, g // 16, b // 16) for r, g, b in pixels)
    palette = [
        {"rgb_bin": list(key), "representative_rgb": [v * 16 + 8 for v in key],
         "pixel_count": n, "fraction": n / count}
        for key, n in sorted(bins.items(), key=lambda p: (-p[1], p[0]))[:8]
    ]
    entropy = -math.fsum((n / count) * math.log2(n / count) for n in bins.values())
    histogram = [0] * 16
    for v in luminance:
        histogram[min(15, int(v * 16))] += 1

    def reflection_error(horizontal):
        return math.fsum(
            abs(luminance[y * width + x] -
                luminance[y * width + (width - 1 - x) if horizontal
                          else (height - 1 - y) * width + x])
            for y in range(height) for x in range(width)
        ) / count

    return {
        "schema": "klone.local_art_image_study.v1",
        "source": {"sha256": hashlib.sha256(data).hexdigest(),
                   "format": image_format, "oriented_size": original_size},
        "analysis_size": [width, height],
        "metrics": {
            "mean_relative_luminance": mean,
            "luminance_population_sd": math.sqrt(variance),
            "luminance_histogram_counts": histogram,
            "occupied_rgb_bins": len(bins),
            "rgb_bin_entropy_bits": max(0.0, entropy),
            "dominant_rgb_bins": palette,
            "dominant_bin_coverage": sum(p["pixel_count"] for p in palette) / count,
            "left_right_luminance_reflection_error": reflection_error(True),
            "top_bottom_luminance_reflection_error": reflection_error(False),
        },
        "limitations": [
            "Still PNG/JPEG only; 16 MiB and four million decoded pixels maximum.",
            "EXIF orientation applied; alpha composited over white in encoded RGB.",
            "RGB values interpreted as sRGB; embedded color profiles not converted.",
            "BOX thumbnail maximum 256 pixels per side; small details may be lost.",
            "Palette uses fixed encoded RGB bins, not perceptually uniform clustering.",
            "Relative luminance assumes sRGB, not measured display brightness.",
            "Reflection errors describe luminance only, not aesthetic quality.",
            "No object recognition, identity analysis, personal inference or memory write.",
            "Content fingerprint is not authenticated provenance; reproducibility depends on decoder.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, help="Explicit local PNG or JPEG artwork")
    args = parser.parse_args(argv)
    try:
        result = analyze_image(args.image)
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        parser.exit(2, "Image analysis failed: " + str(exc) + "\n")
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
