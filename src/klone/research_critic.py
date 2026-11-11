from __future__ import annotations

from dataclasses import dataclass
import re

from .research_compare import ResearchComparison


@dataclass(frozen=True)
class SourceCritique:
    status: str
    observations: tuple[str, ...]
    limitations: tuple[str, ...]


def critique_comparison(comparison: ResearchComparison) -> SourceCritique:
    """Rule-based provenance critique; never asserts factual truth."""
    observations = []
    limitations = [
        "Textual changes do not establish factual correctness.",
        "Citation presence does not prove a source supports a claim.",
    ]
    if comparison.unchanged:
        observations.append("Report content and citation metadata are unchanged.")
    else:
        observations.append("Stored report content or citation metadata changed.")
    if comparison.added_citations:
        observations.append(
            f"Added source references: {len(comparison.added_citations)}.")
    if comparison.removed_citations:
        observations.append(
            f"Removed source references: {len(comparison.removed_citations)}.")
        limitations.append("Removed references require manual evidence review.")
    if "[Diff truncated]" in comparison.unified_diff:
        limitations.append("Displayed text diff is incomplete.")
    return SourceCritique(
        "review_needed" if not comparison.unchanged else "unchanged",
        tuple(observations), tuple(limitations),
    )
