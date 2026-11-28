"""Controlled fixed-view fractal art study with self-contained HTML previews."""
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
import tempfile

from .fractal_art import fractal_study
from .artwork_color_metrics import artwork_color_metrics
from .artwork_palette_entropy import palette_entropy, compare_palette_entropy

LEVELS = (8, 24, 48, 96)


def iteration_gallery(size: int = 128) -> dict:
    rows = []
    baseline = None
    with tempfile.TemporaryDirectory(prefix="klone-fractal-study-") as directory:
        path = Path(directory) / "fixture.png"
        for limit in LEVELS:
            report, png = fractal_study(size, limit)
            path.write_bytes(png)
            palette = artwork_color_metrics(path, full_histogram=True)["full_histogram"]
            if baseline is None:
                baseline = palette
            previous = rows[-1]["unresolved_samples"] if rows else None
            rows.append({
                "iterations": limit,
                "escaped_samples": report["escaped_samples"],
                "unresolved_samples": report["unresolved_samples"],
                "newly_resolved_since_previous": (
                    None if previous is None else previous - report["unresolved_samples"]
                ),
                "unresolved_fraction": report["unresolved_fraction"],
                "palette_entropy": palette_entropy(palette),
                "palette_total_variation_from_first": compare_palette_entropy(
                    baseline, palette)["total_variation"],
                "preview_png_base64": base64.b64encode(png).decode("ascii"),
            })
    return {
        "schema": "klone.fractal_iteration_gallery.v1",
        "dimensions": [size, size],
        "observations": rows,
        "limitations": [
            "Fixed viewport, sample grid and coloring rule; only iteration limit changes.",
            "Finite unresolved samples do not prove membership in the Mandelbrot set.",
            "Palette measurements use sampled encoded RGB, not geometric complexity.",
            "No aesthetic quality score or independent scientific validation.",
        ],
    }


def render_gallery(report: dict) -> str:
    from html import escape
    cards = []
    for row in report["observations"]:
        png = base64.b64encode(base64.b64decode(
            row["preview_png_base64"], validate=True)).decode("ascii")
        level = escape(str(row["iterations"]))
        newly = row["newly_resolved_since_previous"]
        metrics = (
            ("Escaped samples", row["escaped_samples"]),
            ("Unresolved samples", row["unresolved_samples"]),
            ("Newly resolved", "Baseline" if newly is None else newly),
            ("Unresolved fraction", f'{row["unresolved_fraction"]:.2%}'),
            ("Palette entropy (bits)", row["palette_entropy"]["entropy_bits"]),
            ("Palette distance from first", row["palette_total_variation_from_first"]),
        )
        cards.append("<article><h2>Iterations: " + level + "</h2>"
                     "<img alt='Fixed-view fractal, iteration limit " + level
                     + "' src='data:image/png;base64," + png + "'><dl>"
                     + "".join("<dt>" + escape(key) + "</dt><dd>"
                               + escape(str(value)) + "</dd>" for key, value in metrics)
                     + "</dl></article>")
    return ("<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            "<title>KLONE Fractal Iteration Gallery</title><style>"
            ":root{color-scheme:light dark}*{box-sizing:border-box}"
            "body{font:16px/1.5 system-ui,sans-serif;max-width:70rem;margin:1rem auto;padding:0 1rem}"
            ".gallery{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,16rem),1fr));gap:1rem}"
            "article{border:1px solid #888;border-radius:.75rem;padding:1rem}"
            "img{width:100%;height:auto;aspect-ratio:1;image-rendering:pixelated}"
            "dd{margin:0 0 .5rem;font-weight:bold}h2{font-size:1.2rem}"
            "</style></head><body><main><h1>KLONE Fractal Iteration Gallery</h1>"
            "<div class='gallery'>" + "".join(cards) + "</div><h2>Limitations</h2><ul>"
            + "".join("<li>" + escape(s) + "</li>" for s in report["limitations"])
            + "</ul></main></body></html>")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", type=int, default=128)
    parser.add_argument("--format", choices=("json", "html"), default="json")
    args = parser.parse_args(argv)
    try:
        report = iteration_gallery(args.size)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(render_gallery(report) if args.format == "html"
          else json.dumps(report, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
