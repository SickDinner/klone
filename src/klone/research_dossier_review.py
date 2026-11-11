"""Read-only dossier review and deterministic contradiction triage.

This component never infers genetic relationships or source authenticity.
"""
from __future__ import annotations

from dataclasses import dataclass

from .genomics_hypotheses import EvidenceItem, Hypothesis, evaluate_hypotheses
from .research_dossier import ResearchDossier, build_dossier, compare_dossiers


@dataclass(frozen=True)
class DossierReview:
    fingerprint: str
    evidence_count: int
    contradictions: tuple[str, ...]
    unresolved: tuple[str, ...]
    dependency_collisions: tuple[str, ...]
    conclusion: str


def review_dossier(dossier: ResearchDossier) -> DossierReview:
    if not isinstance(dossier, ResearchDossier):
        raise ValueError("Invalid dossier")
    verified = build_dossier(version=dossier.version, hypotheses=dossier.hypotheses,
                             evidence=dossier.evidence)
    if verified.fingerprint != dossier.fingerprint:
        raise ValueError("Dossier integrity mismatch")
    results = evaluate_hypotheses(dossier.hypotheses, dossier.evidence)
    contradictions = tuple(sorted(
        item["hypothesis_id"] for item in results["results"]
        if item["contradiction_groups"] > 0))
    unresolved = tuple(sorted(
        item["hypothesis_id"] for item in results["results"]
        if item["support_groups"] == 0 or item["uncertain_groups"] > 0))
    grouped: dict[tuple[str, str], set[str]] = {}
    for e in dossier.evidence:
        grouped.setdefault((e.hypothesis_id, e.dependency_group), set()).add(e.stance)
    collisions = tuple(sorted(
        f"{hypothesis_id}:{group}" for (hypothesis_id, group), stances in grouped.items()
        if len(stances) > 1))
    return DossierReview(
        dossier.fingerprint, len(dossier.evidence), contradictions,
        unresolved, collisions, "manual_review_required")
