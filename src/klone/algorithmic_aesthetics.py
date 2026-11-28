"""Educational comparison of descriptive statistics on fixed binary artwork."""
from __future__ import annotations

import argparse
from itertools import combinations
import json

from .spatial_information import spatial_information_study


def aesthetics_study():
    """Compare fixed fixtures, without scoring their aesthetic merit."""
    source = spatial_information_study()
    profiles = []
    for row in source["observations"]:
        h, v = row["horizontal"], row["vertical"]
        profiles.append({
            "pattern": row["pattern"],
            "pixel_entropy": round(row["pixel_entropy_bits"], 8),
            "conditional_entropy": [
                round(s["conditional_second_given_first_bits"], 8) for s in (h, v)],
            "mutual_information": [
                round(s["mutual_information_bits"], 8) for s in (h, v)],
            "directional_pair_counts": [s["joint_counts"] for s in (h, v)],
        })
    metrics = ("pixel_entropy", "conditional_entropy",
               "mutual_information", "directional_pair_counts")
    pairs = list(combinations(profiles, 2))
    comparisons = []
    for metric in metrics:
        matching = [[a["pattern"], b["pattern"]] for a, b in pairs
                    if a[metric] == b[metric]]
        comparisons.append({
            "metric": metric,
            "matching_pairs": matching,
            "matching_pair_count": len(matching),
            "distinct_pair_count": len(pairs) - len(matching),
            "total_pair_count": len(pairs),
        })
    return {
        "schema": "klone.algorithmic_aesthetics.v1",
        "dimensions": source["dimensions"],
        "profiles": profiles,
        "comparisons": comparisons,
        "limitations": [
            "Only five fixed synthetic artworks, not a representative art corpus.",
            "Entropy statistics rounded to eight decimal places before comparison.",
            "Ordered directional counts are compared exactly.",
            "Matching metrics do not establish visual identity or perceptual similarity.",
            "More discriminating statistics are not necessarily better artistic descriptors.",
            "No artistic quality score or ranking.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    print(json.dumps(aesthetics_study(), indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
