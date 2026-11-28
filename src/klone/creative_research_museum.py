"""Fixed local educational exhibition of synthetic art, original music and verse."""
from __future__ import annotations

import argparse
import base64
from html import escape
import json

from .creative_universe import creative_universe
from .creative_genome import creative_genome_study
from .creative_evolution_atlas import evolution_atlas
from .mathematical_symmetry import symmetry_study
from .synesthetic_art import render_synesthetic_svg, synesthetic_wav
from .nordic_poetry import DEMO, poetry_study
from .musical_mathematics import tuning_study
from .algorithmic_aesthetics import aesthetics_study


def research_museum():
    base = creative_universe()["exhibits"]
    art = [item for item in base if item["media_type"].startswith("image/")]
    music = [item for item in base if item["media_type"] == "audio/wav"]
    studies = []
    for prefix, rows, name_key in (
        ("genome", creative_genome_study()["observations"], "pattern"),
        ("atlas", evolution_atlas()["observations"], "offset_pixels"),
        ("symmetry", symmetry_study()["observations"], "operation"),
    ):
        for index, row in enumerate(rows):
            studies.append({
                "id": f"{prefix}-{index}",
                "title": prefix.title() + ": " + str(row[name_key]),
                "description": "Fixed synthetic artwork variation.",
                "media_type": "image/png",
                "media_base64": row["preview_png_base64"],
            })
    prelude = [
        {
            "id": "prelude-svg", "title": "Octagonal Prelude: geometry",
            "description": "Eight-note score represented by geometric radii.",
            "media_type": "image/svg+xml",
            "media_base64": base64.b64encode(render_synesthetic_svg().encode()).decode(),
        },
        {
            "id": "prelude-wav", "title": "Octagonal Prelude: sound",
            "description": "Original two-second miniature from the same score.",
            "media_type": "audio/wav",
            "media_base64": base64.b64encode(synesthetic_wav()).decode(),
        },
    ]
    poem = poetry_study(DEMO)
    tuning = tuning_study()
    metrics = aesthetics_study()
    panels = [
        {
            "id": "poetry", "title": "Nordic Poetry",
            "description": "Original demonstration verse and written-language counts.",
            "text": DEMO,
            "facts": [
                ["Lines", poem["line_count"]],
                ["Words", poem["word_count"]],
                ["Written vowel groups", sum(r["written_vowel_groups"] for r in poem["lines"])],
            ],
        },
        {
            "id": "tuning", "title": "Musical Mathematics",
            "description": "Selected pure intervals minus equal temperament, in cents.",
            "facts": [[r["interval"], round(r["just_minus_equal_cents"], 6)]
                      for r in tuning["intervals"]],
        },
        {
            "id": "metrics", "title": "Algorithmic Aesthetics",
            "description": "Distinct pairs out of ten fixed synthetic artwork pairs.",
            "facts": [[r["metric"], r["distinct_pair_count"]] for r in metrics["comparisons"]],
        },
    ]
    return {
        "schema": "klone.creative_research_museum.v1",
        "rooms": [
            {"id": "mathematics", "title": "Mathematical Art", "media": art, "panels": []},
            {"id": "music", "title": "Original Music", "media": music, "panels": []},
            {"id": "variations", "title": "Controlled Variations", "media": studies, "panels": []},
            {"id": "synesthesia", "title": "Audiovisual Art", "media": prelude, "panels": []},
            {"id": "research", "title": "Research Notes", "media": [], "panels": panels},
        ],
        "limitations": [
            "Fixed local educational exhibits; no external input, assets or network.",
            "Original synthetic artwork, music and demonstration verse.",
            "No artistic quality rankings, author inference or physiological claims.",
            "Written vowel groups are not phonetic syllables.",
            "Metric comparisons are limited to the selected fixtures.",
        ],
    }


def render_museum():
    """Render only the fixed internally generated exhibition."""
    report = research_museum()
    links = []
    sections = []
    for room in report["rooms"]:
        key = escape(room["id"], quote=True)
        title = escape(room["title"])
        links.append(f'<a href="#{key}">{title}</a>')
        cards = []
        for item in room["media"]:
            name = escape(item["title"], quote=True)
            medium = item["media_type"]
            if medium not in ("image/svg+xml", "image/png", "audio/wav"):
                raise ValueError("Unexpected museum medium")
            encoded = base64.b64encode(base64.b64decode(
                item["media_base64"], validate=True)).decode("ascii")
            uri = f"data:{medium};base64,{encoded}"
            if medium == "audio/wav":
                content = f'<audio controls preload="none" aria-label="{name}" src="{uri}">Audio unavailable.</audio>'
            else:
                description = escape(item["description"], quote=True)
                content = f'<img loading="lazy" alt="{name}. {description}" src="{uri}">'
            cards.append(f"<article><h3>{name}</h3>{content}<p>"
                         + escape(item["description"]) + "</p></article>")
        for panel in room["panels"]:
            content = "<p>" + escape(panel["description"]) + "</p>"
            if "text" in panel:
                content += '<pre lang="fi">' + escape(panel["text"]) + "</pre>"
            content += "<dl>" + "".join("<dt>" + escape(str(k)) + "</dt><dd>"
                                        + escape(str(v)) + "</dd>"
                                        for k, v in panel["facts"]) + "</dl>"
            cards.append("<article><h3>" + escape(panel["title"]) + "</h3>" + content + "</article>")
        sections.append(f'<section id="{key}" aria-labelledby="{key}-heading"><h2 id="{key}-heading">{title}</h2><div class="gallery">'
                        + "".join(cards) + "</div></section>")
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>KLONE Creative Research Museum</title><style>'
        ':root{color-scheme:light dark}*{box-sizing:border-box}'
        'body{font:16px/1.5 system-ui;max-width:76rem;margin:1rem auto;padding:0 1rem}'
        'nav{display:flex;flex-wrap:wrap;gap:.5rem}section{margin:2rem 0;scroll-margin-top:1rem}'
        'nav a{display:inline-flex;align-items:center;min-height:44px;padding:.5rem .75rem;'
        'text-decoration:underline;overflow-wrap:anywhere}'
        'a:focus-visible,audio:focus-visible{outline:3px solid currentColor;outline-offset:3px}'
        '.gallery{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,17rem),1fr));gap:1rem}'
        'article{border:1px solid #888;border-radius:.75rem;padding:1rem;min-width:0}'
        'img{display:block;width:100%;height:auto;max-height:20rem;object-fit:contain}'
        'audio{width:100%;max-width:100%}pre{white-space:pre-wrap;font:inherit;overflow-wrap:anywhere}'
        'dt,dd,h3,p{overflow-wrap:anywhere}dd{margin:0 0 .5rem}'
        '</style></head><body><main><h1>KLONE Creative Research Museum</h1>'
        '<p>Five curated rooms of mathematical art, original music and research.</p>'
        '<nav aria-label="Museum rooms">' + "".join(links) + "</nav>"
        + "".join(sections) + "<h2>Limitations</h2><ul>"
        + "".join("<li>" + escape(s) + "</li>" for s in report["limitations"])
        + "</ul></main></body></html>"
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("html", "json"), default="html")
    args = parser.parse_args(argv)
    print(render_museum() if args.format == "html" else
          json.dumps(research_museum(), indent=2, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
