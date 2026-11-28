"""Offline HTML presentation of the fixed V10.12 art research synthesis.

No server, external assets, scripts, media ingestion or production integration.
All study text is escaped before insertion into the document.
"""
from __future__ import annotations

import argparse
from html import escape
import json

from .art_synthesis_study import synthesis_study


CSS = """
:root{color-scheme:dark;--bg:#101521;--panel:#192231;--line:#34445a;
--ink:#eef3fa;--muted:#b6c4d7;--accent:#8dd4da}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:16px/1.55 system-ui,sans-serif}main{max-width:1120px;margin:auto;padding:24px}
header{padding:24px 0;border-bottom:1px solid var(--line)}
h1{font-size:clamp(1.6rem,5vw,2.5rem);margin:0 0 8px}h2{margin-top:32px}
h3{margin:0 0 10px}p{margin:8px 0}a{color:var(--accent)}
nav{display:flex;flex-wrap:wrap;gap:16px;margin:16px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:12px}
.tile,article,details,.scope{background:var(--panel);border:1px solid var(--line);
border-radius:10px;padding:16px;margin:10px 0}
.tile strong{display:block;font-size:1.9rem;color:var(--accent)}
.small,caption{color:var(--muted);font-size:.9rem}
.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;text-align:left}
caption{text-align:left;padding:8px 0}th,td{padding:9px;border-bottom:1px solid var(--line);
vertical-align:top}th{color:var(--accent)}code,pre{font-family:ui-monospace,monospace}
code{overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere;
font-size:.85rem;max-height:460px;overflow:auto}summary{cursor:pointer;font-weight:600}
li{margin:5px 0}.status{font-weight:700}.supported_in_fixtures{color:#9ce1ba}
.contradicted_in_fixtures{color:#ffb1ad}.not_assessed,.not_demonstrated{color:#e8ce98}
:focus-visible{outline:2px solid var(--accent);outline-offset:4px}
@media(max-width:480px){main{padding:14px}.tile,article,details,.scope{padding:12px}}
@media print{:root{color-scheme:light;--bg:white;--panel:white;--ink:black;
--muted:#333;--line:#aaa;--accent:#123}nav{display:none}.tile,article{break-inside:avoid}}
"""

STATUS_LABELS = {
    "supported_in_fixtures": "Supported in fixtures",
    "contradicted_in_fixtures": "Contradicted in fixtures",
    "not_assessed": "Not assessed",
    "not_demonstrated": "Not demonstrated",
}


def _e(value):
    return escape(str(value), quote=True)


def _json(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)


def _list(values):
    return "<ul>" + "".join("<li>" + _e(v) + "</li>" for v in values) + "</ul>"


def _table(headers, rows, caption):
    out = ['<div class="scroll"><table><caption>', _e(caption), '</caption><thead><tr>']
    out.extend('<th scope="col">' + _e(h) + '</th>' for h in headers)
    out.append("</tr></thead><tbody>")
    for row in rows:
        out.append("<tr>")
        out.extend("<td>" + _e(v) + "</td>" for v in row)
        out.append("</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def render_report(report):
    """Render a synthesis payload as a self-contained, static HTML document."""
    s = report["summary"]
    scope = report["scope"]
    studies = report["studies"]
    review = next(r["payload"] for r in studies if r["version"] == "10.11")
    out = [
        '<!doctype html><html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">',
        '<title>KLONE V11.1 | Art research laboratory</title><style>', CSS,
        '</style></head><body><main><header>',
        '<p class="small">KLONE / CREATIVE RESEARCH / V11.1 LAB</p>',
        '<h1>Art research laboratory</h1>',
        '<p>Fixed synthetic fixtures. Offline descriptive report; not an aesthetic ranking.</p>',
        '</header><nav aria-label="Report sections">',
        '<a href="#overview">Overview</a><a href="#findings">Findings</a>',
        '<a href="#review">Claim review</a><a href="#sources">Source reports</a>',
        '<a href="#limits">Scope and limitations</a></nav>',
        '<section id="overview"><h2>Research inventory</h2><div class="grid">',
    ]
    for label, key in (
        ("Study reports", "study_count"), ("Cross-domain profiles", "cross_domain_profile_count"),
        ("Cross-domain pairs", "cross_domain_pair_count"), ("Catalog revisions", "catalog_revision_count"),
        ("Complete descriptor matches", "catalog_complete_match_count"),
        ("Review evidence items", "review_evidence_item_count"),
    ):
        out.extend(['<div class="tile"><strong>', _e(s[key]), '</strong>', _e(label), '</div>'])
    out.extend(['</div><p class="small">Counts overlap across reports; not independent experiments.</p></section>',
                '<section id="findings"><h2>Structural findings</h2>'])
    out.append(_table(("Example", "Syllables", "Total (ms)", "Duration CV"),
        [(r["example"], r["illustrative_syllables"], r["total_ms"], r["duration_cv"])
         for r in s["verse_timing_examples"]], "Illustrative verse timing, not recorded speech"))
    out.append(_table(("Color model", "Maximal pair"),
        [(k, ", ".join(v)) for k,v in s["color_maximal_examples"].items()],
        "Within-model maxima; distances across scales are not pooled"))
    out.append(_table(("Descriptor", "Exact matches", "Undefined comparisons"),
        [(k, s["exact_descriptor_match_counts"].get(k, 0),
          s["undefined_descriptor_counts"].get(k, 0))
         for k in sorted(set(s["exact_descriptor_match_counts"]) |
                         set(s["undefined_descriptor_counts"]))],
        "Cross-domain comparisons; undefined descriptors are not zero values"))
    out.extend(['<p class="small">Common comparisons cover spatial, rhythm and spectrum only. ',
                'Verse and color are separate studies.</p></section>',
                '<section id="review"><h2>Claim review</h2><div class="grid">'])
    for status, count in sorted(s["review_status_counts"].items()):
        out.extend(['<div class="tile"><strong>', _e(count), '</strong>',
                    _e(STATUS_LABELS.get(status, status)), '</div>'])
    out.append('</div><p class="small">Deterministic checks, not independent reviewers or human ratings.</p>')
    for claim in review["reviews"]:
        status = claim["status"]
        safe_class = status if status in STATUS_LABELS else ""
        out.extend(['<article><h3>', _e(claim["id"]), '</h3><p>', _e(claim["claim"]),
                    '</p><p class="status ', safe_class, '">', _e(STATUS_LABELS.get(status, status)),
                    '</p><p>', _e(claim["scope_limit"]), '</p><details><summary>Evidence (',
                    _e(len(claim["evidence"])), ')</summary><pre>', _e(_json(claim["evidence"])),
                    '</pre></details></article>'])
    out.extend(['</section><section id="sources"><h2>Source reports</h2>',
                '<p>Original payloads, fingerprints and source-specific limitations.</p>'])
    for study in studies:
        payload = study["payload"]
        out.extend(['<details><summary>V', _e(study["version"]), ' / ', _e(study["domain"]),
                    '</summary><p>Schema: <code>', _e(study["source_schema"]),
                    '</code></p><p>SHA-256: <code>', _e(study["payload_sha256"]),
                    '</code></p><h3>Source limitations</h3>', _list(payload["limitations"]),
                    '<details><summary>Full original JSON payload</summary><pre>',
                    _e(_json(payload)), '</pre></details></details>'])
    out.extend(['</section><section id="limits"><h2>Scope and limitations</h2>',
                '<div class="scope"><pre>', _e(_json(scope)), '</pre></div>',
                _list(report["limitations"]),
                '<p>Fingerprints describe serialized content, not authenticated provenance.</p>',
                '</section><footer class="small">KLONE V11.1 / Static offline LAB report</footer>',
                '</main></body></html>'])
    return "".join(out)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    print(render_report(synthesis_study()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
