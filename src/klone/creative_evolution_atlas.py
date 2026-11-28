"""An educational atlas of fixed abstract artwork variations."""
from __future__ import annotations

import argparse
import base64
from html import escape
import io
import json
from pathlib import Path
import tempfile

from PIL import Image, ImageDraw
from .artwork_color_metrics import artwork_color_metrics
from .artwork_palette_entropy import compare_palette_entropy, palette_entropy

SIZE = 64
OFFSETS = (0, 4, 8, 16)
BACKGROUND = (21, 35, 54)
FOREGROUND = (234, 184, 86)


def _artwork(offset):
    image = Image.new("RGB", (SIZE, SIZE), BACKGROUND)
    ImageDraw.Draw(image).rectangle((8 + offset, 16, 23 + offset, 47), fill=FOREGROUND)
    return image


def evolution_atlas():
    """Four fixed variations with identical colors and rectangle dimensions."""
    baseline = None
    original = _artwork(0)
    observations = []
    with tempfile.TemporaryDirectory(prefix="klone-art-atlas-") as directory:
        path = Path(directory) / "fixture.png"
        for offset in OFFSETS:
            image = _artwork(offset)
            image.save(path, format="PNG")
            histogram = artwork_color_metrics(path, full_histogram=True)["full_histogram"]
            if baseline is None:
                baseline = histogram
            changed = sum(
                original.getpixel((x, y)) != image.getpixel((x, y))
                for y in range(SIZE) for x in range(SIZE)
            )
            observations.append({
                "offset_pixels": offset,
                "palette": palette_entropy(histogram),
                "palette_distance_from_first": compare_palette_entropy(
                    baseline, histogram)["total_variation"],
                "changed_pixels_from_first": changed,
                "changed_pixel_fraction": changed / (SIZE * SIZE),
                "preview_png_base64": base64.b64encode(path.read_bytes()).decode("ascii"),
            })
    return {
        "schema": "klone.creative_evolution_atlas.v1",
        "dimensions": [SIZE, SIZE],
        "experiment": "fixed_abstract_rectangle_translation",
        "observations": observations,
        "limitations": [
            "Fixed synthetic abstract artwork; no external input.",
            "Only horizontal placement varies; rectangle size and color remain fixed.",
            "Palette statistics ignore spatial arrangement; aligned pixel differences do not.",
            "No inference of perceptual similarity, artistic quality or biological evolution.",
        ],
    }


def render_atlas(report):
    cards = []
    for row in report["observations"]:
        offset = escape(str(row["offset_pixels"]))
        encoded = base64.b64encode(base64.b64decode(
            row["preview_png_base64"], validate=True)).decode("ascii")
        metrics = (
            ("Palette entropy (bits)", f'{row["palette"]["entropy_bits"]:.8f}'),
            ("Palette distance", f'{row["palette_distance_from_first"]:.6f}'),
            ("Changed pixels", str(row["changed_pixels_from_first"])),
            ("Changed pixel fraction", f'{row["changed_pixel_fraction"]:.2%}'),
        )
        cards.append("<article><h2>Offset " + offset + "</h2>"
                     "<img alt='Abstract rectangle variation, offset " + offset
                     + "' src='data:image/png;base64," + encoded + "'><dl>"
                     + "".join("<dt>" + escape(k) + "</dt><dd>" + escape(v)
                               + "</dd>" for k, v in metrics) + "</dl></article>")
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<title>KLONE Creative Evolution Atlas</title><style>"
        ":root{color-scheme:light dark}*{box-sizing:border-box}"
        "body{font:16px/1.5 system-ui;max-width:70rem;margin:1rem auto;padding:0 1rem}"
        ".gallery{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,16rem),1fr));gap:1rem}"
        "article{min-width:0;border:1px solid #888;border-radius:.75rem;padding:1rem}"
        "img{display:block;width:100%;height:auto;image-rendering:pixelated}"
        "dd{margin:0 0 .5rem;font-weight:bold}h2{font-size:1.2rem}"
        "</style></head><body><main><h1>KLONE Creative Evolution Atlas</h1>"
        "<p>One controlled variation: position in an abstract composition.</p>"
        "<div class='gallery'>" + "".join(cards) + "</div><h2>Limitations</h2><ul>"
        + "".join("<li>" + escape(s) + "</li>" for s in report["limitations"])
        + "</ul></main></body></html>"
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("json", "html"), default="html")
    args = parser.parse_args(argv)
    report = evolution_atlas()
    print(render_atlas(report) if args.format == "html"
          else json.dumps(report, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
