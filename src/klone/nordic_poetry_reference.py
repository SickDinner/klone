"""Small authored Finnish verse reference demonstration, not a linguistic gold corpus."""
from __future__ import annotations

import argparse
import json
from collections import Counter

from .verse_reference_study import evaluate_verse_reference

# Original examples and explicit illustrative annotations supplied during development.
# Hyphens mark the proposed syllable boundaries; spaces separate words.
FIXTURES = (
    ("regular", "Kuu paistaa", "kuu pais-taa"),
    ("regular", "Tuuli kulkee", "tuu-li kul-kee"),
    ("regular", "Yö on tyyni", "yö on tyy-ni"),
    ("regular", "Metsä herää", "met-sä he-rää"),
    ("regular", "Järvi jäätyy", "jär-vi jää-tyy"),
    ("regular", "Kivi lepää", "ki-vi le-pää"),
    ("hiatus", "Radio soi", "ra-di-o soi"),
    ("hiatus", "Piano soi", "pi-a-no soi"),
    ("hiatus", "Video alkaa", "vi-de-o al-kaa"),
    ("hiatus", "Museo avautuu", "mu-se-o a-vau-tuu"),
    ("hiatus", "Idea kasvaa", "i-de-a kas-vaa"),
    ("hiatus", "Teatteri avautuu", "te-at-te-ri a-vau-tuu"),
)


def poetry_reference_demo():
    entries = []
    for category, line, segmentation in FIXTURES:
        if segmentation.replace("-", "").casefold() != line.casefold():
            raise ValueError("Reference segmentation does not reproduce source")
        count = sum(len(word.split("-")) for word in segmentation.split())
        entries.append({"line": line, "reference_syllables": count})
    reference = evaluate_verse_reference(entries)
    examples = []
    by_category = {}
    for (category, line, segmentation), row in zip(FIXTURES, reference["rows"]):
        examples.append({
            "category": category, "line": line, "illustrative_segmentation": segmentation,
            **row,
        })
        by_category.setdefault(category, []).append(row["difference"])
    return {
        "schema": "klone.nordic_poetry_reference_demo.v1",
        "annotation_source": "assistant_authored_illustrative_examples",
        "independent_expert_review": False,
        "example_count": len(examples),
        "summary": {k: v for k, v in reference.items() if k not in ("rows", "limitations")},
        "categories": [{
            "category": category,
            "example_count": len(errors),
            "exact_count_matches": errors.count(0),
            "difference_histogram": {str(k): v for k, v in sorted(Counter(errors).items())},
        } for category, errors in by_category.items()],
        "examples": examples,
        "limitations": [
            "Small deliberately selected demonstration, not a representative Finnish corpus.",
            "Assistant-authored illustrative syllable boundaries, not expert-reviewed annotations.",
            "Pronunciation and syllabification may vary; no phonetic or Kalevala meter verdict.",
            "Results show differences from these proposed reference counts only.",
            "The report includes only the fixed original demonstration text.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    print(json.dumps(poetry_reference_demo(), ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
