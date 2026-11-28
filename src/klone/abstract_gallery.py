"""Controlled synthetic abstract-art experiments with separate descriptive metrics."""
from __future__ import annotations

import argparse
import base64
from html import escape
from io import BytesIO
import json
from pathlib import Path
import tempfile

from PIL import Image, ImageDraw, ImageOps

from .artwork_color_metrics import artwork_color_metrics
from .artwork_palette_study import compare_full_histograms

SIZE = 64


def _fixture():
    image = Image.new("RGB", (SIZE, SIZE), (32, 64, 96))
    draw = ImageDraw.Draw(image)
    draw.rectangle((4, 8, 23, 47), fill=(224, 64, 32))
    draw.rectangle((32, 16, 55, 31), fill=(192, 160, 64))
    return image


def _variants(original):
    return {
        "horizontal_mirror": ImageOps.mirror(original),
        "red_blue_swap": Image.merge("RGB", tuple(reversed(original.split()))),
        "grayscale": ImageOps.grayscale(original).convert("RGB"),
    }


def _png_data(image):
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def abstract_gallery():
    """Run a fixed, synthetic experiment; no user files or external services."""
    original = _fixture()
    images = {"original": original, **_variants(original)}
    with tempfile.TemporaryDirectory(prefix="klone-abstract-gallery-") as directory:
        results = {}
        for label, image in images.items():
            path = Path(directory) / (label + ".png")
            image.save(path)
            results[label] = artwork_color_metrics(path, full_histogram=True)
    before = results["original"]["full_histogram"]
    baseline_pixels = list(original.get_flattened_data()) if hasattr(original, "get_flattened_data") else list(original.getdata())
    observations = []
    for label, image in images.items():
        changed = sum(a != b for a, b in zip(baseline_pixels, image.get_flattened_data() if hasattr(image, "get_flattened_data") else image.getdata()))
        observations.append({
            "variant": label,
            "changed_pixel_fraction": changed / (SIZE * SIZE),
            "palette_distance": compare_full_histograms(
                before, results[label]["full_histogram"]),
            "neutral_fraction": results[label]["neutral_fraction"],
            "preview_png_base64": _png_data(image),
        })
    return {
        "schema": "klone.abstract_gallery.v1",
        "fixture": "fixed_three_color_abstract_rectangles",
        "dimensions": [SIZE, SIZE],
        "observations": observations,
        "limitations": [
            "Synthetic artwork only; each variant is compared to the original.",
            "Palette distance is spatially invariant; changed-pixel fraction compares aligned pixels.",
            "Color swapping and grayscale alter multiple color properties.",
            "Neither metric measures artistic quality, perception or causal effects on viewers.",
        ],
    }


def render_gallery(report):
    cards = []
    for row in report["observations"]:
        name = escape(row["variant"].replace("_", " "))
        png = row["preview_png_base64"]
        # Re-encode validated bytes, never interpolate arbitrary data URL content.
        encoded = base64.b64encode(base64.b64decode(png, validate=True)).decode("ascii")
        distance = escape(str(row["palette_distance"]["total_variation_exact"]))
        changed = f'{row["changed_pixel_fraction"]:.2%}'
        neutral = f'{row["neutral_fraction"]:.2%}'
        cards.append(
            "<article><h2>" + name + "</h2>"
            "<img width='192' height='192' alt='Synthetic abstract color rectangles: " + name
            + "' src='data:image/png;base64," + encoded + "'>"
            "<dl><dt>Palette distance</dt><dd>" + distance
            + "</dd><dt>Changed pixels</dt><dd>" + changed
            + "</dd><dt>Neutral pixels</dt><dd>" + neutral + "</dd></dl></article>"
        )
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>KLONE Counterfactual Gallery</title><style>"
        ":root{color-scheme:light dark}*{box-sizing:border-box}"
        "body{font:16px/1.5 system-ui,sans-serif;max-width:70rem;margin:1rem auto;padding:0 1rem}"
        ".gallery{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,16rem),1fr));gap:1rem}"
        "article{border:1px solid #888;border-radius:.8rem;padding:1rem;min-width:0}"
        "img{width:100%;height:auto;max-width:16rem;image-rendering:pixelated}"
        "h2{font-size:1.2rem}dd{margin:0 0 .5rem;font-weight:bold}"
        "</style></head><body><main><h1>KLONE Counterfactual Gallery</h1>"
        "<p>Controlled synthetic artwork variants</p><div class='gallery'>"
        + "".join(cards) + "</div><h2>Limitations</h2><ul>"
        + "".join("<li>" + escape(note) + "</li>" for note in report["limitations"])
        + "</ul></main></body></html>"
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("json", "html"), default="json")
    args = parser.parse_args(argv)
    report = abstract_gallery()
    print(render_gallery(report) if args.format == "html" else
          json.dumps(report, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
