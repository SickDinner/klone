"""Read-only synthesis of fixed synthetic creative-art studies V10.3–V10.11.

Preserves full study payloads and limitations, without any overall aesthetic
score or claims about human perception. Hashes are reproducibility aids only.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json

from .verse_timing_study import verse_timing_study
from .perceptual_color_study import color_study
from .advanced_color_study import advanced_color_study
from .spatial_composition_study import spatial_study
from .temporal_rhythm_study import rhythm_study
from .musical_spectrum_study import spectrum_study
from .crossmodal_art_structure import crossmodal_study
from .aesthetic_catalog_study import aesthetic_catalog
from .aesthetic_review_study import review_study


def _fingerprint(payload):
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=True, allow_nan=False).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


def synthesis_study():
    studies = (
        ("10.3", "verse", verse_timing_study()),
        ("10.4", "color", color_study()),
        ("10.5", "color", advanced_color_study()),
        ("10.6", "spatial", spatial_study()),
        ("10.7", "rhythm", rhythm_study()),
        ("10.8", "spectrum", spectrum_study()),
        ("10.9", "cross_domain", crossmodal_study()),
        ("10.10", "catalog", aesthetic_catalog()),
        ("10.11", "review", review_study()),
    )
    by_version = {version: payload for version, _, payload in studies}
    verse = by_version["10.3"]["observations"]
    color = by_version["10.5"]["observations"]
    cross = by_version["10.9"]
    catalog = by_version["10.10"]
    review = by_version["10.11"]
    matches = Counter(k for pair in cross["cross_domain_comparisons"]
                      for k in pair["exact_descriptor_matches"])
    undefined = Counter(k for pair in cross["cross_domain_comparisons"]
                        for k in pair["undefined_descriptors"])
    color_maxima = {}
    for key in ("delta_e_76", "delta_e_2000", "oklab_distance"):
        maximum = max(row[key] for row in color)
        color_maxima[key] = sorted(row["example"] for row in color
                                   if row[key] == maximum)
    return {
        "schema": "klone.art_synthesis_study.v1",
        "studies": [
            {"version": version, "domain": domain, "source_schema": payload["schema"],
             "payload_sha256": _fingerprint(payload), "payload": payload}
            for version, domain, payload in studies
        ],
        "summary": {
            "study_count": len(studies),
            "observation_counts_by_version": {
                version: len(payload["observations"])
                for version, _, payload in studies if "observations" in payload
            },
            "verse_timing_examples": [
                {k: row[k] for k in ("example", "illustrative_syllables",
                                      "total_ms", "duration_cv")} for row in verse
            ],
            "color_maximal_examples": color_maxima,
            "cross_domain_profile_count": len(cross["profiles"]),
            "cross_domain_pair_count": len(cross["cross_domain_comparisons"]),
            "exact_descriptor_match_counts": dict(sorted(matches.items())),
            "undefined_descriptor_counts": dict(sorted(undefined.items())),
            "catalog_record_count": len(catalog["records"]),
            "catalog_revision_count": sum(len(r["revisions"]) for r in catalog["records"]),
            "catalog_complete_match_count": len(catalog["cross_domain_descriptor_collisions"]),
            "review_status_counts": dict(review["status_counts"]),
            "review_evidence_item_count": sum(len(r["evidence"]) for r in review["reviews"]),
        },
        "scope": {
            "data_kind": "fixed_synthetic_art_fixtures",
            "empirical_observer_validation": False,
            "overall_aesthetic_score": None,
            "cross_domain_coverage": ["spatial", "rhythm", "spectrum"],
            "verse_and_color_in_common_comparisons": False,
        },
        "limitations": [
            "Nine study reports, not nine independent experiments; some reuse the same fixtures.",
            "Verse and color appear as separate studies, not cross-domain descriptor comparisons.",
            "Preserved payload fingerprints are not signatures, authentication or independent evidence.",
            "The summary is a descriptive inventory, not a ranking or evaluation of artistic quality.",
            "No real media, observer data, preference inference, persistent memory or production integration.",
            "All source limitations remain attached to their original payloads.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", action="store_true",
                        help="Print the summary and scope without full study payloads.")
    args = parser.parse_args(argv)
    report = synthesis_study()
    if args.summary:
        report = {k: report[k] for k in ("schema", "summary", "scope", "limitations")}
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
