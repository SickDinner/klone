"""Educational timing comparison using fixed authored verse annotations.

No recorded speech, speaker inference or phonetic alignment is involved.
"""
from __future__ import annotations

import argparse
import json
import math

from .nordic_poetry_reference import poetry_reference_demo


def verse_timing_study():
    reference = poetry_reference_demo()
    examples = {row["line"]: row for row in reference["examples"]}
    fixtures = (
        ("even", "Radio soi", (250, 250, 250, 250)),
        ("uneven", "Radio soi", (150, 150, 400, 300)),
        ("even_regular", "Tuuli kulkee", (250, 250, 250, 250)),
    )
    rows = []
    for name, line, durations in fixtures:
        source = examples[line]
        syllables = source["illustrative_segmentation"].replace(" ", "-").split("-")
        if len(syllables) != len(durations) or any(d <= 0 for d in durations):
            raise ValueError("Invalid illustrative timing")
        total = sum(durations)
        mean = total / len(durations)
        sd = math.sqrt(sum((d - mean) ** 2 for d in durations) / len(durations))
        events = []
        start = 0
        for syllable, duration in zip(syllables, durations):
            events.append({"syllable": syllable, "start_ms": start, "duration_ms": duration})
            start += duration
        rows.append({
            "example": name,
            "line": line,
            "written_vowel_groups": source["written_vowel_groups"],
            "illustrative_syllables": len(syllables),
            "total_ms": total,
            "mean_duration_ms": mean,
            "duration_population_sd_ms": sd,
            "duration_cv": sd / mean,
            "events": events,
        })
    return {
        "schema": "klone.verse_timing_study.v1",
        "observations": rows,
        "limitations": [
            "Fixed assistant-authored verse and illustrative syllable boundaries.",
            "Assigned synthetic durations, not observed speech or singing.",
            "Equal syllable counts and total durations can coexist with different timing patterns.",
            "No inference about stress, linguistic quantity, speaker identity or performance quality.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    print(json.dumps(verse_timing_study(), ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
