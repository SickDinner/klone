"""Deterministic benchmark for evidence tracking, not model accuracy.

A fixture defines expected source IDs, contradictions and dependencies.
Compare two candidate dossier outputs under exactly the same fixture.
"""
from __future__ import annotations

from dataclasses import dataclass

from .research_dossier import ResearchDossier
from .research_dossier_review import review_dossier


@dataclass(frozen=True)
class BenchmarkFixture:
    expected_evidence_ids: frozenset[str]
    expected_contradiction_ids: frozenset[str]
    expected_dependency_collisions: frozenset[str]


@dataclass(frozen=True)
class BenchmarkScore:
    evidence_precision: float
    evidence_recall: float
    contradiction_precision: float
    contradiction_recall: float
    dependency_precision: float
    dependency_recall: float


def _pr(found: set[str], expected: frozenset[str]) -> tuple[float, float]:
    correct = len(found & expected)
    return (correct / len(found) if found else (1.0 if not expected else 0.0),
            correct / len(expected) if expected else (1.0 if not found else 0.0))


def score_dossier(dossier: ResearchDossier, fixture: BenchmarkFixture) -> BenchmarkScore:
    if not isinstance(fixture, BenchmarkFixture) or not all(
        isinstance(v, frozenset) and all(isinstance(x, str) for x in v)
        for v in (fixture.expected_evidence_ids, fixture.expected_contradiction_ids,
                  fixture.expected_dependency_collisions)
    ):
        raise ValueError("Invalid benchmark fixture")
    review = review_dossier(dossier)
    e = _pr({item.evidence_id for item in dossier.evidence}, fixture.expected_evidence_ids)
    c = _pr(set(review.contradictions), fixture.expected_contradiction_ids)
    d = _pr(set(review.dependency_collisions), fixture.expected_dependency_collisions)
    return BenchmarkScore(*e, *c, *d)
