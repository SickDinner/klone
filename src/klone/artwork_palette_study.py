"""Local comparison of explicitly selected artwork palettes using complete RGB counts."""
from __future__ import annotations

import argparse
from fractions import Fraction
import json
from pathlib import Path

from .artwork_color_metrics import artwork_color_metrics


def _distribution(histogram):
    if not isinstance(histogram, dict) or histogram.get("schema") != "klone.sampled_rgb_counts.v1":
        raise ValueError("Unsupported histogram")
    total = histogram.get("sample_pixels")
    bins = histogram.get("bins")
    if type(total) is not int or not 1 <= total <= 16384:
        raise ValueError("Invalid sample size")
    if not isinstance(bins, list) or not 1 <= len(bins) <= 512:
        raise ValueError("Invalid bin count")
    counts = {}
    for item in bins:
        if not isinstance(item, dict):
            raise ValueError("Invalid bin")
        key = item.get("rgb_bin")
        count = item.get("count")
        if (not isinstance(key, list) or len(key) != 3
                or any(type(x) is not int or not 0 <= x <= 7 for x in key)
                or type(count) is not int or not 1 <= count <= total):
            raise ValueError("Invalid color count")
        key = tuple(key)
        if key in counts:
            raise ValueError("Duplicate bin")
        counts[key] = count
    if sum(counts.values()) != total:
        raise ValueError("Histogram count mismatch")
    return {key: Fraction(value, total) for key, value in counts.items()}


def compare_full_histograms(before, after):
    a, b = _distribution(before), _distribution(after)
    keys = a.keys() | b.keys()
    distance = sum(abs(a.get(k, 0) - b.get(k, 0)) for k in keys) / 2
    return {
        "schema": "klone.artwork_palette_comparison.v1",
        "total_variation": round(float(distance), 8),
        "total_variation_exact": str(distance),
        "shared_occupied_bins": len(a.keys() & b.keys()),
        "status": "descriptive_only",
        "limitations": [
            "Complete counts of sampled encoded RGB bins, not original-resolution pixels.",
            "Spatial composition, perceptual color difference and artistic quality are not measured.",
            "No profile conversion; transparency composited on white after resizing.",
        ],
    }


def palette_study(before: Path, after: Path):
    a = artwork_color_metrics(before, full_histogram=True)
    b = artwork_color_metrics(after, full_histogram=True)
    return {
        "schema": "klone.artwork_palette_study.v1",
        "before": a,
        "after": b,
        "comparison": compare_full_histograms(a["full_histogram"], b["full_histogram"]),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    args = parser.parse_args(argv)
    try:
        result = palette_study(args.before, args.after)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
