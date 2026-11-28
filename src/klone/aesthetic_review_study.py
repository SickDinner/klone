"""Deterministic review of fixed synthetic art-study claims.

Static educational checks, not agent votes or human aesthetic judgments.
The report makes no decisions or changes to production state.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter

from .aesthetic_catalog_study import aesthetic_catalog
from .advanced_color_study import advanced_color_study


def review_study():
    catalog = aesthetic_catalog()
    records = {r["fixture_id"]: r for r in catalog["records"]}
    color = advanced_color_study()

    def revision(name):
        return records[name]["revisions"][1]

    def evidence(name, field, group="domain_context"):
        r = revision(name)
        return {"fixture_id": name, "revision": r["revision"],
                "revision_sha256": r["revision_sha256"],
                "field": group + "." + field, "value": r[group][field]}

    regular = "rhythm:regular_quarters"
    alternating = "rhythm:alternating_gaps"
    soft = "spectrum:soft_harmonics"
    bright = "spectrum:bright_harmonics"
    silent = "spectrum:silence"
    checks = []

    def add(identifier, claim, status, facts, limit):
        checks.append({"id": identifier, "claim": claim, "status": status,
                       "evidence": facts, "scope_limit": limit})

    facts = [evidence(n, "minimal_period_steps") for n in (regular, alternating)]
    common_equal = revision(regular)["common_descriptors"] == revision(alternating)["common_descriptors"]
    add("rhythm_period_collision",
        "Identical common descriptors can conceal different rhythmic periods.",
        "supported_in_fixtures" if common_equal and facts[0]["value"] != facts[1]["value"]
        else "not_demonstrated",
        facts + [evidence(n, k, "common_descriptors") for n in (regular, alternating)
                 for k in revision(n)["common_descriptors"]],
        "Two fixed pulse patterns; no inference about perceived musical similarity.")

    facts = [evidence(n, "harmonic_power_entropy_bits") for n in (soft, bright)]
    common_equal = revision(soft)["common_descriptors"] == revision(bright)["common_descriptors"]
    add("spectral_occupancy_collision",
        "Identical common descriptors can conceal different harmonic power entropy.",
        "supported_in_fixtures" if common_equal and facts[0]["value"] != facts[1]["value"]
        else "not_demonstrated",
        facts + [evidence(n, k, "common_descriptors") for n in (soft, bright)
                 for k in revision(n)["common_descriptors"]],
        "Binary harmonic presence is not a measure of harmonic power distribution.")

    facts = [evidence(silent, "power_centroid_hz"),
             evidence(silent, "ideal_cycle_rms")]
    add("undefined_not_zero",
        "A silent spectrum has zero RMS but no defined power centroid.",
        "supported_in_fixtures" if facts[0]["value"] is None and facts[1]["value"] == 0
        else "not_demonstrated", facts,
        "Silence is a synthetic all-zero spectrum, not a measurement of a recording.")

    keys = ("delta_e_76", "delta_e_2000", "oklab_distance")
    facts = []
    for key in keys:
        values = {r["example"]: r[key] for r in color["observations"]}
        maximum = max(values.values())
        facts.append({"source_schema": color["schema"], "metric": key,
                      "values": values, "maximal_examples":
                          sorted(n for n,v in values.items() if v == maximum)})
    add("color_model_disagreement",
        "All three color-distance models select the same maximal pair.",
        "contradicted_in_fixtures" if len({tuple(f["maximal_examples"]) for f in facts}) > 1
        else "supported_in_fixtures", facts,
        "Compare orderings only; scales differ and no observer preference is measured.")

    collisions = catalog["cross_domain_descriptor_collisions"]
    facts = [{"first_fixture_id": c["first_fixture_id"],
              "second_fixture_id": c["second_fixture_id"],
              "first_source_sha256": records[c["first_fixture_id"]]["source_sha256"],
              "second_source_sha256": records[c["second_fixture_id"]]["source_sha256"]}
             for c in collisions]
    distinct = bool(facts) and all(f["first_source_sha256"] != f["second_source_sha256"]
                                   for f in facts)
    add("source_distinction",
        "Complete descriptor matches can occur between distinct serialized sources.",
        "supported_in_fixtures" if distinct else "not_demonstrated", facts,
        "Content hashes distinguish serialized fixtures, not authorship or authenticity.")

    add("aesthetic_preference",
        "These measurements establish which artwork a person will prefer.",
        "not_assessed", [],
        "No human ratings, observer data, or validated preference model.")
    add("crossmodal_perception",
        "Equal descriptors establish equal subjective experiences across media.",
        "not_assessed", [],
        "No crossmodal experiment; shared mathematical descriptors alone cannot establish this.")

    return {
        "schema": "klone.aesthetic_review_study.v1",
        "source_schemas": [catalog["schema"], color["schema"]],
        "reviews": checks,
        "status_counts": dict(sorted(Counter(c["status"] for c in checks).items())),
        "limitations": [
            "Seven predeclared claims about fixed synthetic art fixtures.",
            "Deterministic checks, not independent reviewers, Council72 votes or model calls.",
            "No aggregate score, preference ranking or subjective aesthetic judgment.",
            "No external input, persistent writes, action execution or production integration.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    print(json.dumps(review_study(), indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
