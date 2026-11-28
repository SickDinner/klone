"""Versioned catalog of fixed synthetic art-study profiles.

This is a read-only educational report, not a personal or agent memory
service. Revision 2 adds domain-specific context to revision 1.
"""
from __future__ import annotations

import argparse
import hashlib
import json

from .crossmodal_art_structure import crossmodal_study
from .spatial_composition_study import PATTERNS as SPATIAL, composition
from .temporal_rhythm_study import PATTERNS as RHYTHMS, rhythm_metrics
from .musical_spectrum_study import FIXTURES as SPECTRA, spectrum_metrics


def _digest(value):
    data = json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")
    return hashlib.sha256(data).hexdigest()


def _fixtures():
    rows = {}
    for name, raster in SPATIAL:
        rows["spatial", name] = (
            {"raster": list(raster)}, "klone.spatial_composition_study.v1",
            composition(raster),
            ("foreground_component_count_4", "normalized_centroid_offset",
             "left_right_agreement", "top_bottom_agreement"))
    for name, pattern in RHYTHMS:
        rows["rhythm", name] = (
            {"pattern": pattern}, "klone.temporal_rhythm_study.v1",
            rhythm_metrics(pattern),
            ("minimal_period_steps", "gap_entropy_bits",
             "gap_coefficient_of_variation", "canonical_rotation"))
    for name, frequency, amplitudes in SPECTRA:
        rows["spectrum", name] = (
            {"fundamental_grid_hz": frequency, "relative_peak_amplitudes": list(amplitudes)},
            "klone.musical_spectrum_study.v1", spectrum_metrics(frequency, amplitudes),
            ("power_centroid_hz", "power_spread_hz",
             "harmonic_power_entropy_bits", "ideal_cycle_rms"))
    return rows


def _revision(number, common, context, previous):
    body = {"revision": number, "common_descriptors": dict(common),
            "domain_context": dict(context), "previous_revision_sha256": previous}
    return {**body, "revision_sha256": _digest(body)}


def aesthetic_catalog():
    study = crossmodal_study()
    fixtures = _fixtures()
    records = []
    for profile in study["profiles"]:
        domain, name = profile["domain"], profile["example"]
        source, schema, metrics, keys = fixtures[domain, name]
        common = profile["features"]
        r1 = _revision(1, common, {}, None)
        r2 = _revision(2, common, {k: metrics[k] for k in keys},
                       r1["revision_sha256"])
        records.append({
            "fixture_id": domain + ":" + name,
            "source_schema": schema,
            "source_fixture": source,
            "source_sha256": _digest({"schema": schema, "fixture": source}),
            "revisions": [r1, r2],
        })
    by_id = {r["fixture_id"]: r for r in records}
    collisions = []
    for pair in study["cross_domain_comparisons"]:
        if len(pair["exact_descriptor_matches"]) != 3:
            continue
        first, second = (":".join(pair[k]) for k in ("first", "second"))
        collisions.append({
            "first_fixture_id": first, "second_fixture_id": second,
            "matching_descriptors": list(pair["exact_descriptor_matches"]),
            "distinct_source_fingerprints":
                by_id[first]["source_sha256"] != by_id[second]["source_sha256"],
            "interpretation": "descriptor_match_only",
        })
    return {
        "schema": "klone.aesthetic_catalog_study.v1",
        "source_comparison_schema": study["schema"],
        "records": records,
        "cross_domain_descriptor_collisions": collisions,
        "limitations": [
            "Only fixed synthetic art fixtures; no personal media, external inputs or database.",
            "Two constructed report revisions, not observations of change over time.",
            "SHA-256 fingerprints describe serialized content; not signed provenance or authentication.",
            "Revision 2 preserves original descriptors and adds non-comparable domain-specific context.",
            "Exact descriptor matches do not establish artistic or perceptual identity.",
            "Missing values remain null; no imputation, composite score or inferred preference.",
            "No persistent writes, agent integration or production memory changes.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    print(json.dumps(aesthetic_catalog(), indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
