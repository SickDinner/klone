"""Controlled educational artwork profiles, using only fixed synthetic patterns."""
from __future__ import annotations

import argparse
import base64
import io
import json
from pathlib import Path
import tempfile

from PIL import Image
from .artwork_color_metrics import artwork_color_metrics
from .artwork_palette_entropy import palette_entropy, compare_palette_entropy

SIZE = 32
PATTERNS = ("vertical_split", "horizontal_split", "checkerboard", "vertical_stripes")
COLORS = ((21, 35, 54), (234, 184, 86))


def _grid(name):
    if name not in PATTERNS:
        raise ValueError("Unknown synthetic pattern")
    return [
        [
            int(x >= SIZE // 2) if name == "vertical_split"
            else int(y >= SIZE // 2) if name == "horizontal_split"
            else (x + y) % 2 if name == "checkerboard"
            else x % 2
            for x in range(SIZE)
        ]
        for y in range(SIZE)
    ]


def _spatial(grid):
    n = SIZE
    pairs = n * (n - 1)
    horizontal = sum(grid[y][x] != grid[y][x + 1]
                     for y in range(n) for x in range(n - 1))
    vertical = sum(grid[y][x] != grid[y + 1][x]
                   for y in range(n - 1) for x in range(n))
    return {
        "horizontal_neighbor_difference_fraction": horizontal / pairs,
        "vertical_neighbor_difference_fraction": vertical / pairs,
        "left_right_mirror_match_fraction": sum(
            grid[y][x] == grid[y][n - 1 - x]
            for y in range(n) for x in range(n)) / (n * n),
        "top_bottom_mirror_match_fraction": sum(
            grid[y][x] == grid[n - 1 - y][x]
            for y in range(n) for x in range(n)) / (n * n),
    }


def creative_genome_study():
    """Compare equal-color synthetic fixtures without claiming aesthetic quality."""
    rows = []
    baseline_grid = _grid(PATTERNS[0])
    baseline_palette = None
    with tempfile.TemporaryDirectory(prefix="klone-genome-study-") as directory:
        path = Path(directory) / "fixture.png"
        for name in PATTERNS:
            grid = _grid(name)
            image = Image.new("RGB", (SIZE, SIZE))
            image.putdata([COLORS[v] for row in grid for v in row])
            image.save(path, format="PNG")
            histogram = artwork_color_metrics(path, full_histogram=True)["full_histogram"]
            if baseline_palette is None:
                baseline_palette = histogram
            rows.append({
                "pattern": name,
                "palette": palette_entropy(histogram),
                "palette_distance_from_first": compare_palette_entropy(
                    baseline_palette, histogram)["total_variation"],
                "aligned_pixel_difference_from_first": sum(
                    grid[y][x] != baseline_grid[y][x]
                    for y in range(SIZE) for x in range(SIZE)) / (SIZE * SIZE),
                "spatial": _spatial(grid),
                "preview_png_base64": base64.b64encode(path.read_bytes()).decode("ascii"),
            })
    return {
        "schema": "klone.creative_genome_study.v1",
        "dimensions": [SIZE, SIZE],
        "observations": rows,
        "limitations": [
            "Four fixed synthetic mathematical artworks; no external image input.",
            "Genome is a metaphor for a descriptive feature profile, not biological data.",
            "Neighbor metrics exclude wraparound; mirror metrics compare aligned binary states.",
            "Pixel distance depends on alignment; palette statistics ignore spatial arrangement.",
            "No combined quality score, perceptual similarity or author inference.",
        ],
    }


def render_genome_html(report):
    from html import escape
    cards = []
    for row in report["observations"]:
        name = escape(row["pattern"].replace("_", " "))
        png = base64.b64encode(base64.b64decode(
            row["preview_png_base64"], validate=True)).decode("ascii")
        metrics = {
            "Palette entropy (bits)": row["palette"]["entropy_bits"],
            "Palette distance": row["palette_distance_from_first"],
            "Aligned pixel difference": row["aligned_pixel_difference_from_first"],
            **{k.replace("_", " "): v for k, v in row["spatial"].items()},
        }
        cards.append("<article><h2>" + name + "</h2><img alt='" + name
                     + "' src='data:image/png;base64," + png + "'><dl>"
                     + "".join("<dt>" + escape(k) + "</dt><dd>"
                               + escape(f"{v:.6f}") + "</dd>"
                               for k, v in metrics.items()) + "</dl></article>")
    return ("<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            "<title>Creative Genome Study</title><style>"
            ":root{color-scheme:light dark}*{box-sizing:border-box}"
            "body{font:16px/1.5 system-ui;max-width:70rem;margin:1rem auto;padding:0 1rem}"
            ".gallery{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,16rem),1fr));gap:1rem}"
            "article{border:1px solid #888;border-radius:.75rem;padding:1rem}"
            "img{width:100%;height:auto;image-rendering:pixelated}"
            "dd{margin:0 0 .5rem;font-weight:bold}h2{font-size:1.2rem}"
            "</style></head><body><main><h1>Creative Genome Study</h1>"
            "<p>Equal palettes, different spatial arrangements.</p><div class='gallery'>"
            + "".join(cards) + "</div><h2>Limitations</h2><ul>"
            + "".join("<li>" + escape(s) + "</li>" for s in report["limitations"])
            + "</ul></main></body></html>")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("json", "html"), default="json")
    args = parser.parse_args(argv)
    report = creative_genome_study()
    print(render_genome_html(report) if args.format == "html"
          else json.dumps(report, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
