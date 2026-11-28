"""Offline descriptive color statistics for explicitly supplied artwork."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from PIL import Image, ImageOps

MAX_PIXELS = 4_000_000
SAMPLE_SIDE = 128


def artwork_color_metrics(path: Path, *, full_histogram: bool = False) -> dict:
    """Analyze a bounded PNG/JPEG; composite transparency on white."""
    with Image.open(path) as source:
        if source.format not in {"PNG", "JPEG"}:
            raise ValueError("Expected PNG or JPEG artwork")
        if source.width * source.height > MAX_PIXELS or getattr(source, "n_frames", 1) != 1:
            raise ValueError("Artwork exceeds pixel or frame limit")
        source = ImageOps.exif_transpose(source)
        rgba = source.convert("RGBA")
    rgba.thumbnail((SAMPLE_SIDE, SAMPLE_SIDE), Image.Resampling.LANCZOS)
    background = Image.new("RGBA", rgba.size, "white")
    rgb = Image.alpha_composite(background, rgba).convert("RGB")
    colors = list(rgb.getdata()) if not hasattr(rgb, "get_flattened_data") else list(rgb.get_flattened_data())
    count = len(colors)
    bins = Counter()
    neutral = 0
    for red, green, blue in colors:
        bins[(red // 32, green // 32, blue // 32)] += 1
        neutral += max(red, green, blue) - min(red, green, blue) <= 16
    dominant = sorted(bins.items(), key=lambda item: (-item[1], item[0]))[:8]
    report = {
        "schema": "klone.artwork_color_metrics.v1",
        "sample_dimensions": list(rgb.size),
        "sample_pixels": count,
        "neutral_fraction": round(neutral / count, 8),
        "occupied_rgb_bins": len(bins),
        "dominant_bins": [
            {"rgb_bin": list(key), "fraction": round(value / count, 8)}
            for key, value in dominant
        ],
        "limitations": [
            "Descriptive encoded RGB bins, not a perceptually uniform color space.",
            "No color-profile conversion; transparency composited on white after resizing.",
            "Top eight bins only; fractions may not sum to one.",
            "No object recognition or aesthetic quality inference.",
        ],
    }
    if full_histogram:
        report["full_histogram"] = {
            "schema": "klone.sampled_rgb_counts.v1",
            "sample_pixels": count,
            "bins": [{"rgb_bin": list(key), "count": value}
                     for key, value in sorted(bins.items())],
        }
    return report
