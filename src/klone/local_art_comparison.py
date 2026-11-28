"""Descriptive pairwise comparison of explicitly selected local artworks.

Only same-medium pairs; order is caller-selected, not inferred chronology.
No quality scores, personal inference, automatic linking or persistent writes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import wave

from PIL import Image
from .local_creative_archive import creative_archive


def compare_artworks(kind, first, second):
    archive = creative_archive([(kind, first), (kind, second)])
    records = {r["record_id"]: r for r in archive["records"]}
    a, b = (records[s["record_id"]] for s in archive["selections"])
    return _compare_records(a, b)


def _compare_records(a, b):
    """Compare internally generated artwork records without rereading media."""
    kind = a["media_kind"]
    if kind not in ("image", "audio", "lyrics") or b["media_kind"] != kind:
        raise ValueError("comparison requires two records of the same artwork kind")
    if a["report_schema"] != b["report_schema"]:
        raise ValueError("comparison requires matching report schemas")
    x, y = a["report"], b["report"]
    metrics = []

    def add(name, before, after, unit, compatible=True, note=None):
        if not compatible:
            status = "context_mismatch"
        elif before is None or after is None:
            status = "undefined"
        else:
            status = "comparable"
        metrics.append({
            "metric": name, "first": before, "second": after, "unit": unit,
            "status": status,
            "delta_second_minus_first": after-before if status == "comparable" else None,
            "note": note,
        })

    if kind == "image":
        context = {"first_analysis_size": x["analysis_size"],
                   "second_analysis_size": y["analysis_size"]}
        compatible = x["analysis_size"] == y["analysis_size"]
        for field, unit in (
            ("mean_relative_luminance", "fraction"),
            ("luminance_population_sd", "fraction"),
            ("occupied_rgb_bins", "count"),
            ("rgb_bin_entropy_bits", "bit"),
            ("dominant_bin_coverage", "fraction"),
            ("left_right_luminance_reflection_error", "fraction"),
            ("top_bottom_luminance_reflection_error", "fraction"),
        ):
            add(field, x["metrics"][field], y["metrics"][field], unit,
                compatible, "Equal analysis dimensions required by this comparison.")
    elif kind == "audio":
        fields = ("sample_rate_hz", "channels", "frames")
        context = {side: {k: r["source"][k] for k in fields}
                   for side, r in (("first", x), ("second", y))}
        compatible = context["first"] == context["second"]
        add("duration_seconds", x["source"]["duration_seconds"],
            y["source"]["duration_seconds"], "s")
        for i in range(max(len(x["channel_metrics"]), len(y["channel_metrics"]))):
            c1 = x["channel_metrics"][i] if i < len(x["channel_metrics"]) else {}
            c2 = y["channel_metrics"][i] if i < len(y["channel_metrics"]) else {}
            for field, unit in (("peak", "fraction_full_scale"),
                                ("rms", "fraction_full_scale"),
                                ("crest_factor", "ratio")):
                add("channel_" + str(i+1) + "." + field,
                    c1.get(field), c2.get(field), unit, compatible,
                    "Equal sample rate, channel count and frame count required.")
        add("sampled_power_centroid_hz",
            x["sampled_spectrum"]["power_centroid_hz"],
            y["sampled_spectrum"]["power_centroid_hz"], "Hz", compatible,
            "Sampled rectangular-window spectra; equal recording dimensions required.")
    else:
        context = {"first_word_count": x["lexical_metrics"]["word_count"],
                   "second_word_count": y["lexical_metrics"]["word_count"]}
        for group, field, unit in (
            ("structure", "lyric_line_count", "count"),
            ("structure", "stanza_count", "count"),
            ("lexical_metrics", "word_count", "count"),
            ("lexical_metrics", "distinct_word_forms", "count"),
            ("lexical_metrics", "type_token_ratio", "fraction"),
            ("lexical_metrics", "repeated_normalized_line_fraction", "fraction"),
            ("lexical_metrics", "adjacent_initial_match_fraction", "fraction"),
            ("line_end_metrics", "distinct_end_word_suffix_match_fraction", "fraction"),
        ):
            note = ("Length-sensitive descriptive statistic; not vocabulary skill."
                    if field == "type_token_ratio" else
                    "Written patterns only, not phonetic rhyme or artistic quality.")
            add(field, x[group][field], y[group][field], unit, note=note)

    return {
        "schema": "klone.local_art_comparison.v1",
        "media_kind": kind,
        "first_record": {k: a[k] for k in ("record_id","source_sha256","report_sha256","report_schema")},
        "second_record": {k: b[k] for k in ("record_id","source_sha256","report_sha256","report_schema")},
        "same_source_bytes": a["source_sha256"] == b["source_sha256"],
        "comparison_context": context,
        "metrics": metrics,
        "source_limitations": list(x["limitations"]),
        "limitations": [
            "Two explicitly selected artworks of the same medium.",
            "Order is caller-selected; no chronology or revision relationship inferred.",
            "Signed differences are descriptive, not evidence of improvement or decline.",
            "Context mismatches and undefined values produce null deltas, never imputed zeros.",
            "Matching contexts do not prove perceptual or empirical comparability.",
            "No aggregate score, identity inference, raw media export or persistent writes.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("image","audio","lyrics"))
    parser.add_argument("first", type=Path)
    parser.add_argument("second", type=Path)
    args = parser.parse_args(argv)
    try:
        report = compare_artworks(args.kind,args.first,args.second)
    except (OSError, ValueError, EOFError, wave.Error, Image.DecompressionBombError) as exc:
        parser.exit(2, "Comparison failed: " + str(exc) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
