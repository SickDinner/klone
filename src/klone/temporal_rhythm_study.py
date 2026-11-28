"""Deterministic study of fixed synthetic musical pulse patterns.

A one represents a note onset on an equal-duration cyclic grid.
No audio, external inputs, listener experiment or aesthetic score.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math

PATTERNS = (
    ("regular_quarters", "1000100010001000"),
    ("clustered_four", "1111000000000000"),
    ("alternating_gaps", "1010000010100000"),
    ("asymmetric_four", "1001000100001000"),
    ("rotated_quarters", "0100010001000100"),
    ("alternating_pulses", "1010101010101010"),
    ("single_onset", "1000000000000000"),
    ("silent", "0000000000000000"),
    ("all_onsets", "1111111111111111"),
)


def _entropy(counts):
    total = sum(counts)
    return -sum((c/total)*math.log2(c/total) for c in counts if c) if total else None


def rhythm_metrics(pattern):
    """Structural metrics for a nonempty string of binary musical pulses."""
    if not isinstance(pattern, str) or not pattern or any(c not in "01" for c in pattern):
        raise ValueError("expected a nonempty binary pulse string")
    n = len(pattern)
    onsets = [i for i, c in enumerate(pattern) if c == "1"]
    k = len(onsets)
    gaps = ([b-a for a,b in zip(onsets, onsets[1:])]
            + [n+onsets[0]-onsets[-1]]) if k else []
    hist = Counter(gaps)
    period = next(p for p in range(1,n+1)
                  if n % p == 0 and pattern == pattern[:p]*(n//p))
    rotations = [pattern[i:]+pattern[:i] for i in range(n)]
    transitions = sum(pattern[i] != pattern[(i+1)%n] for i in range(n))
    overlaps = [sum(pattern[i] == "1" and pattern[(i+lag)%n] == "1"
                    for i in range(n)) for lag in range(n)]
    mean = n/k if k else None
    cv = math.sqrt(sum((g-mean)**2 for g in gaps)/k)/mean if k else None
    return {
        "grid_steps": n,
        "onset_count": k,
        "onset_density": k/n,
        "binary_entropy_bits": _entropy([k,n-k]),
        "cyclic_interonset_gaps_steps": gaps,
        "gap_histogram": [{"steps": g, "count": hist[g]} for g in sorted(hist)],
        "gap_entropy_bits": _entropy(list(hist.values())),
        "gap_mean_steps": mean,
        "gap_coefficient_of_variation": cv,
        "minimal_period_steps": period,
        "repetitions": n//period,
        "canonical_rotation": min(rotations),
        "cyclic_transition_count": transitions,
        "cyclic_transition_fraction": transitions/n,
        "cyclic_onset_overlap_counts": overlaps,
        "cyclic_onset_overlap_fraction": [v/k for v in overlaps] if k else None,
    }


def rhythm_study():
    return {
        "schema": "klone.temporal_rhythm_study.v1",
        "observations": [{"example": name, "pattern": p, "metrics": rhythm_metrics(p)}
                         for name,p in PATTERNS],
        "limitations": [
            "Nine fixed synthetic binary musical onset patterns; no audio input.",
            "Cyclic equal-duration grid; no accents, meter, tempo, timbre or microtiming.",
            "Gap statistics undefined for silence; single onset has a full-cycle gap.",
            "Rotation canonicalization discards absolute phase, not meter-aware equivalence.",
            "Overlap is uncentered circular onset overlap, not Pearson correlation.",
            "Entropy, variability and periodicity describe structure, not perceived groove or beauty.",
            "No production integration or consciousness claim.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    print(json.dumps(rhythm_study(), indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
