"""Educational D4 symmetry of a square and a fixed synthetic artwork."""
from __future__ import annotations

import argparse
import base64
from html import escape
import io
import json

from PIL import Image, ImageDraw

SIZE = 48
NAMES = ("identity", "rotate90", "rotate180", "rotate270",
         "mirror", "mirror_rotate90", "mirror_rotate180", "mirror_rotate270")


def transform_point(x: int, y: int, operation: str, size: int = SIZE):
    """Reflect left-right first when requested, then rotate clockwise."""
    if operation not in NAMES:
        raise ValueError("Unknown D4 operation")
    if type(size) is not int or not 2 <= size <= 256:
        raise ValueError("Invalid square size")
    if any(type(v) is not int or not 0 <= v < size for v in (x, y)):
        raise ValueError("Point outside square")
    index = NAMES.index(operation)
    if index >= 4:
        x = size - 1 - x
    for _ in range(index % 4):
        x, y = size - 1 - y, x
    return x, y


def compose(first: str, second: str) -> str:
    """Return the operation that applies first, then second."""
    corners = ((0, 0), (1, 0), (1, 1), (0, 1))
    signature = tuple(transform_point(*transform_point(x, y, first, 2), second, 2)
                      for x, y in corners)
    return next(name for name in NAMES
                if tuple(transform_point(x, y, name, 2) for x, y in corners) == signature)


def _fixture():
    image = Image.new("RGB", (SIZE, SIZE), (21, 35, 54))
    draw = ImageDraw.Draw(image)
    draw.rectangle((5, 7, 13, 30), fill=(234, 184, 86))
    draw.rectangle((21, 12, 38, 18), fill=(130, 229, 216))
    return image


def symmetry_study():
    original = _fixture()
    observations = []
    for name in NAMES:
        image = Image.new("RGB", (SIZE, SIZE))
        for y in range(SIZE):
            for x in range(SIZE):
                image.putpixel(transform_point(x, y, name), original.getpixel((x, y)))
        changed = sum(original.getpixel((x, y)) != image.getpixel((x, y))
                      for y in range(SIZE) for x in range(SIZE))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        observations.append({
            "operation": name,
            "inverse": next(other for other in NAMES if compose(name, other) == "identity"),
            "changed_pixels": changed,
            "changed_pixel_fraction": changed / (SIZE * SIZE),
            "color_counts_preserved": sorted(original.getcolors()) == sorted(image.getcolors()),
            "preview_png_base64": base64.b64encode(buffer.getvalue()).decode("ascii"),
        })
    return {
        "schema": "klone.mathematical_symmetry.v1",
        "group": "D4",
        "dimensions": [SIZE, SIZE],
        "operations": list(NAMES),
        "composition_convention": "row first, column second",
        "composition_table": [[compose(a, b) for b in NAMES] for a in NAMES],
        "observations": observations,
        "limitations": [
            "Fixed synthetic abstract artwork, no external input.",
            "Exact square-grid permutations, no interpolation.",
            "Aligned pixel difference is not perceptual or artistic quality.",
            "D4 here means the eight symmetries of a square, not a biological model.",
        ],
    }


def render_symmetry_html(report):
    cards = []
    for row in report["observations"]:
        name = escape(row["operation"])
        encoded = base64.b64encode(base64.b64decode(
            row["preview_png_base64"], validate=True)).decode("ascii")
        cards.append("<article><h2>" + name + "</h2><img alt='" + name
                     + "' src='data:image/png;base64," + encoded + "'>"
                     "<p>Inverse: " + escape(row["inverse"]) + "</p>"
                     "<p>Changed pixels: " + escape(str(row["changed_pixels"]))
                     + "</p></article>")
    names = report["operations"]
    table = ("<table><caption>Composition: row first, column second</caption><thead>"
             "<tr><th scope='col'>First / second</th>"
             + "".join("<th scope='col'>" + escape(n) + "</th>" for n in names)
             + "</tr></thead><tbody>"
             + "".join("<tr><th scope='row'>" + escape(n) + "</th>"
                       + "".join("<td>" + escape(v) + "</td>" for v in row)
                       + "</tr>" for n, row in zip(names, report["composition_table"]))
             + "</tbody></table>")
    return ("<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>KLONE Mathematical Symmetry</title><style>"
            ":root{color-scheme:light dark}*{box-sizing:border-box}"
            "body{font:16px/1.5 system-ui;max-width:70rem;margin:1rem auto;padding:0 1rem}"
            ".gallery{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,14rem),1fr));gap:1rem}"
            "article{border:1px solid #888;border-radius:.75rem;padding:1rem;min-width:0}"
            "img{width:100%;height:auto;image-rendering:pixelated}h2{font-size:1.2rem}"
            ".scroll{overflow-x:auto}table{border-collapse:collapse}"
            "th,td{border:1px solid #888;padding:.4rem;text-align:left}"
            "</style></head><body><main><h1>KLONE Mathematical Symmetry</h1>"
            "<div class='gallery'>" + "".join(cards) + "</div>"
            "<h2>D4 composition table</h2><div class='scroll'>" + table
            + "</div><h2>Limitations</h2><ul>"
            + "".join("<li>" + escape(s) + "</li>" for s in report["limitations"])
            + "</ul></main></body></html>")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("json", "html"), default="html")
    args = parser.parse_args(argv)
    report = symmetry_study()
    print(render_symmetry_html(report) if args.format == "html"
          else json.dumps(report, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
