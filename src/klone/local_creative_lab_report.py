"""Self-contained local creative laboratory report, using explicit artwork selections.

No server, JavaScript, remote assets, original media embedding or database writes.
"""
from __future__ import annotations

import argparse
from html import escape
import json
from pathlib import Path
import wave

from PIL import Image
from .local_creative_archive import creative_archive
from .local_art_comparison import compare_artworks
from .art_metric_validation import validation_study

MAX_COMPARISONS = 3
CSS = """
:root{color-scheme:dark;--bg:#101521;--panel:#192231;--line:#394960;--ink:#edf2fa;--muted:#b9c7da;--accent:#8dd4da}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 system-ui,sans-serif}
main{max-width:1120px;margin:auto;padding:22px}header{border-bottom:1px solid var(--line);padding:18px 0}
h1{font-size:clamp(1.7rem,5vw,2.6rem);margin:0}h2{margin-top:32px}h3{margin-top:4px}
a{color:var(--accent)}nav{display:flex;flex-wrap:wrap;gap:14px;margin:16px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:10px}
.tile,article,details{background:var(--panel);border:1px solid var(--line);border-radius:9px;padding:14px;margin:10px 0}
.tile strong{display:block;font-size:1.8rem;color:var(--accent)}
.muted,caption{color:var(--muted);font-size:.9rem}summary{cursor:pointer;font-weight:600}
.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;text-align:left}caption{text-align:left;padding:6px 0}
th,td{border-bottom:1px solid var(--line);padding:8px;vertical-align:top}th{color:var(--accent)}
code,pre{font-family:ui-monospace,monospace;overflow-wrap:anywhere}
pre{white-space:pre-wrap;max-height:420px;overflow:auto;font-size:.85rem}
:focus-visible{outline:2px solid var(--accent);outline-offset:4px}
@media(max-width:480px){main{padding:12px}article,details,.tile{padding:10px}}
@media print{:root{color-scheme:light;--bg:white;--panel:white;--ink:black;--muted:#333;--line:#aaa;--accent:#123}nav{display:none}}
"""


def _e(value):
    return escape(str(value), quote=True)


def _value(value):
    if value is None:
        return "Undefined"
    if isinstance(value, float):
        return format(value, ".8g")
    return str(value)


def _json(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)


def _details(label, value):
    return "<details><summary>" + _e(label) + "</summary><pre>" + _e(_json(value)) + "</pre></details>"


def _table(headers, rows, caption):
    out = ['<div class="scroll"><table><caption>',_e(caption),'</caption><thead><tr>']
    out.extend('<th scope="col">'+_e(v)+'</th>' for v in headers)
    out.append('</tr></thead><tbody>')
    for row in rows:
        out.append('<tr>')
        out.extend('<td>'+_e(_value(v))+'</td>' for v in row)
        out.append('</tr>')
    out.append('</tbody></table></div>')
    return "".join(out)


def _limits(values):
    return "<ul>" + "".join("<li>"+_e(v)+"</li>" for v in values) + "</ul>"


def _record_summary(record):
    kind, r = record["media_kind"], record["report"]
    if kind == "image":
        m = r["metrics"]
        rows = [(k,m[k]) for k in ("mean_relative_luminance","luminance_population_sd",
                "occupied_rgb_bins","rgb_bin_entropy_bits","left_right_luminance_reflection_error",
                "top_bottom_luminance_reflection_error")]
        return (_table(("Descriptor","Value"),rows,"Image descriptors") +
                _table(("Representative RGB","Fraction"),
                       [(p["representative_rgb"],p["fraction"]) for p in m["dominant_rgb_bins"]],
                       "Fixed RGB palette bins"))
    if kind == "audio":
        rows = [("duration_seconds",r["source"]["duration_seconds"]),
                ("sample_rate_hz",r["source"]["sample_rate_hz"]),
                ("sampled_power_centroid_hz",r["sampled_spectrum"]["power_centroid_hz"])]
        return (_table(("Descriptor","Value"),rows,"Audio descriptors") +
                _table(("Channel","Peak","RMS","Crest factor"),
                       [(i+1,c["peak"],c["rms"],c["crest_factor"])
                        for i,c in enumerate(r["channel_metrics"])],"Digital channel levels"))
    if kind == "lyrics":
        rows = [("lyric_line_count",r["structure"]["lyric_line_count"]),
                ("stanza_count",r["structure"]["stanza_count"])]
        rows += [(k,r["lexical_metrics"][k]) for k in ("word_count","distinct_word_forms",
                 "type_token_ratio","repeated_normalized_line_fraction","adjacent_initial_match_fraction")]
        rows.append(("distinct_end_word_suffix_match_fraction",
                     r["line_end_metrics"]["distinct_end_word_suffix_match_fraction"]))
        return _table(("Descriptor","Value"),rows,"Written lyric descriptors")
    raise ValueError("unsupported artwork kind")


def render_lab(archive, comparisons, validation):
    inv = archive["inventory"]
    out = [
        '<!doctype html><html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">',
        '<title>KLONE V11.8 | Creative laboratory</title><style>',CSS,
        '</style></head><body><main><header><p class="muted">KLONE / CREATIVE LAB / V11.8</p>',
        '<h1>Local creative laboratory</h1><p>Descriptive artwork research, not a quality ranking.</p></header>',
        '<nav aria-label="Report sections"><a href="#inventory">Inventory</a><a href="#artworks">Artworks</a>',
        '<a href="#comparisons">Comparisons</a><a href="#validation">Validation</a>',
        '<a href="#limits">Scope</a></nav><section id="inventory"><h2>Collection inventory</h2><div class="grid">',
    ]
    for label,value in (("Selections",inv["selection_count"]),
                        ("Unique records",inv["unique_record_count"]),
                        ("Duplicate selections",inv["duplicate_selection_count"]),
                        ("Comparisons",len(comparisons))):
        out.extend(['<div class="tile"><strong>',_e(value),'</strong>',_e(label),'</div>'])
    out.extend(['</div>',_table(("Medium","Records"),inv["records_by_media_kind"].items(),"Collection by medium"),
                _table(("Selection","Record identifier","Duplicate"),
                       [(s["selection_index"],s["record_id"],s["duplicate_within_collection"])
                        for s in archive["selections"]],"Selection accounting"),
                '</section><section id="artworks"><h2>Artwork profiles</h2>'])
    for i, record in enumerate(archive["records"],1):
        out.extend(['<article><h3>Artwork ',_e(i),' / ',_e(record["media_kind"]),'</h3>',
                    '<p>Source SHA-256: <code>',_e(record["source_sha256"]),'</code></p>',
                    '<p>Report SHA-256: <code>',_e(record["report_sha256"]),'</code></p>',
                    _record_summary(record), _details("Complete artwork record",record), '</article>'])
    out.extend(['</section><section id="comparisons"><h2>Explicit artwork comparisons</h2>',
                '<p>Order is caller-selected. Differences are descriptive, not improvements or declines.</p>'])
    if not comparisons:
        out.append("<p>No comparisons selected.</p>")
    for i,r in enumerate(comparisons,1):
        out.extend(['<article><h3>Comparison ',_e(i),' / ',_e(r["media_kind"]),'</h3>',
                    '<p>First: <code>',_e(r["first_record"]["record_id"]),'</code></p>',
                    '<p>Second: <code>',_e(r["second_record"]["record_id"]),'</code></p>',
                    _table(("Metric","First","Second","Delta","Unit","Status"),
                           [(m["metric"],m["first"],m["second"],m["delta_second_minus_first"],
                             m["unit"],m["status"]) for m in r["metrics"]],
                           "Signed differences; undefined or mismatched deltas are not zeros"),
                    _details("Complete comparison report",r),'</article>'])
    out.extend(['</section><section id="validation"><h2>Controlled synthetic validation</h2>',
                '<p>These checks concern predefined synthetic fixtures, not the selected artworks or human observers.</p>',
                _table(("Check","Domain","Status","Scope"),
                       [(c["id"],c["domain"],c["status"],c["scope"]) for c in validation["checks"]],
                       "Numerical validation outcomes"),
                _details("Complete validation report",validation),
                '</section><section id="limits"><h2>Scope and limitations</h2>',
                _limits(archive["limitations"]),_limits(validation["limitations"]),
                '<p>Original media and file paths are not included. Fingerprints are not authenticated provenance.</p>',
                _details("Complete collection report",archive),'</section>',
                '<footer class="muted">KLONE V11.8 / Offline static report</footer></main></body></html>'])
    return "".join(out)


def build_lab(items, comparisons=()):
    if len(comparisons) > MAX_COMPARISONS:
        raise ValueError("at most three explicit comparisons")
    archive = creative_archive(items)
    reports = [compare_artworks(kind,first,second) for kind,first,second in comparisons]
    validation = validation_study()
    return render_lab(archive,reports,validation), validation["status_counts"].get("failed",0)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--item",nargs=2,action="append",required=True,metavar=("KIND","PATH"))
    parser.add_argument("--compare",nargs=3,action="append",default=[],metavar=("KIND","FIRST","SECOND"))
    args = parser.parse_args(argv)
    try:
        document, failures = build_lab(args.item,args.compare)
    except (OSError, ValueError, EOFError, wave.Error, Image.DecompressionBombError) as exc:
        parser.exit(2,"Lab report failed: "+str(exc)+"\n")
    print(document)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
