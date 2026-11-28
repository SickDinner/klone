"""Compare written Finnish verse rhythm proxies with supplied human annotations.

This is a descriptive study of creative verse, not a phonetic syllabifier.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from .written_verse_rhythm import written_verse_rhythm

MAX_BYTES = 262144
MAX_ENTRIES = 1000
MAX_LINE_LENGTH = 500
MAX_REFERENCE = 500


def evaluate_verse_reference(entries: list) -> dict:
    if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_ENTRIES:
        raise ValueError("Expected 1 to 1000 annotated verse entries")
    rows = []
    errors = []
    for i, entry in enumerate(entries, 1):
        if not isinstance(entry, dict):
            raise ValueError("Expected verse entry object")
        line = entry.get("line")
        if (not isinstance(line, str) or not 1 <= len(line) <= MAX_LINE_LENGTH
                or len(line.splitlines()) != 1 or not line.strip()):
            raise ValueError("Expected one bounded nonblank verse line")
        reference = entry.get("reference_syllables")
        if reference is not None and (
            type(reference) is not int or not 1 <= reference <= MAX_REFERENCE
        ):
            raise ValueError("Invalid reference syllable count")
        rhythm = written_verse_rhythm(line)
        if rhythm["line_count"] != 1:
            raise ValueError("Expected verse content, not a section marker")
        observed = rhythm["written_vowel_groups_per_line"][0]
        delta = observed - reference if reference is not None else None
        if delta is not None:
            errors.append(delta)
        rows.append({"line_index": i, "written_vowel_groups": observed,
                     "reference_syllables": reference, "difference": delta})
    count = len(errors)
    histogram = Counter(errors)
    return {
        "schema": "klone.verse_reference_study.v1",
        "line_count": len(rows),
        "annotated_lines": count,
        "unannotated_lines": len(rows) - count,
        "exact_count_matches": sum(e == 0 for e in errors),
        "exact_match_fraction": round(sum(e == 0 for e in errors) / count, 8) if count else None,
        "mean_absolute_difference": round(sum(abs(e) for e in errors) / count, 8) if count else None,
        "mean_signed_difference": round(sum(errors) / count, 8) if count else None,
        "difference_histogram": {str(k): v for k, v in sorted(histogram.items())},
        "rows": rows,
        "limitations": [
            "Reference counts are supplied by the operator and are not independently verified.",
            "Written vowel groups are not phonetic syllables or a meter classification.",
            "Results describe only the supplied annotated lines; missing references are excluded.",
            "No original verse text included; counts are not an anonymization guarantee.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    try:
        with args.path.open("rb") as source:
            raw = source.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("Reference input exceeds byte limit")
        result = evaluate_verse_reference(json.loads(raw.decode("utf-8")))
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
