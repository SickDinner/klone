"""Conservative temporal evidence calculus for public ancient DNA metadata.

This is interval arithmetic, not radiocarbon calibration, Bayesian dating,
population ancestry, relatedness or a historical migration inference.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .genomics_public import PublicSample, validate_public_sample


@dataclass(frozen=True)
class TemporalComparison:
    left_accession: str
    right_accession: str
    overlap_years: int
    union_years: int
    overlap_fraction: Fraction
    possible_order: str
    comparable_assay: bool
    interpretation: str


def compare_intervals(left: PublicSample, right: PublicSample) -> TemporalComparison:
    validate_public_sample(left)
    validate_public_sample(right)
    a0, a1 = left.period_start_ce, left.period_end_ce
    b0, b1 = right.period_start_ce, right.period_end_ce
    # Inclusive integer calendar-year ranges. No year-zero correction or BCE/CE
    # calendrical transformation is inferred from these declared coordinates.
    overlap = max(0, min(a1, b1) - max(a0, b0) + 1)
    union = max(a1, b1) - min(a0, b0) + 1
    order = ("left_before_right" if a1 < b0
             else "right_before_left" if b1 < a0
             else "overlapping_or_ambiguous")
    return TemporalComparison(
        left.accession, right.accession, overlap, union,
        Fraction(overlap, union), order,
        left.assembly == right.assembly and left.assay == right.assay,
        "interval_metadata_only_no_migration_or_kinship_inference",
    )


def temporal_pairwise(samples: tuple[PublicSample, ...], *, max_samples: int = 200) -> tuple[TemporalComparison, ...]:
    if not isinstance(samples, tuple) or type(max_samples) is not int or not 1 <= max_samples <= 200:
        raise ValueError("Invalid sample collection or limit")
    if len(samples) > max_samples:
        raise ValueError("Too many samples for bounded pairwise comparison")
    for sample in samples:
        validate_public_sample(sample)
    keys = [(sample.source, sample.accession) for sample in samples]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate accession")
    ordered = sorted(samples, key=lambda sample: (sample.source, sample.accession))
    return tuple(compare_intervals(ordered[i], ordered[j])
                 for i in range(len(ordered)) for j in range(i + 1, len(ordered)))
