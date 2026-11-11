"""Deterministic public-source research dossier and evidence delta.

A human or separately trusted importer supplies source references and stances.
No automatic historical inference, genetic kinship determination or web crawl.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json

from .genomics_hypotheses import EvidenceItem, Hypothesis, evaluate_hypotheses


@dataclass(frozen=True)
class ResearchDossier:
    version: int
    hypotheses: tuple[Hypothesis, ...]
    evidence: tuple[EvidenceItem, ...]
    fingerprint: str


def build_dossier(*, version: int, hypotheses: tuple[Hypothesis, ...],
                  evidence: tuple[EvidenceItem, ...]) -> ResearchDossier:
    if type(version) is not int or version < 1:
        raise ValueError("Invalid dossier version")
    evaluation = evaluate_hypotheses(hypotheses, evidence)
    if not hypotheses:
        raise ValueError("At least one hypothesis required")
    return ResearchDossier(version, hypotheses, evidence, evaluation["fingerprint"])


def compare_dossiers(old: ResearchDossier, new: ResearchDossier) -> dict[str, object]:
    """Explicitly preserve retractions and contradiction history, never overwrite."""
    if not isinstance(old, ResearchDossier) or not isinstance(new, ResearchDossier):
        raise ValueError("Expected dossiers")
    if type(old.version) is not int or type(new.version) is not int or new.version <= old.version:
        raise ValueError("Dossier version must increase")
    for dossier in (old, new):
        checked = build_dossier(version=dossier.version, hypotheses=dossier.hypotheses,
                                evidence=dossier.evidence)
        if checked.fingerprint != dossier.fingerprint:
            raise ValueError("Dossier fingerprint mismatch")
    old_h = {h.hypothesis_id: h for h in old.hypotheses}
    new_h = {h.hypothesis_id: h for h in new.hypotheses}
    old_e = {e.evidence_id: e for e in old.evidence}
    new_e = {e.evidence_id: e for e in new.evidence}
    changed = tuple(sorted(k for k in old_e.keys() & new_e.keys()
                           if old_e[k] != new_e[k]))
    old_eval = evaluate_hypotheses(old.hypotheses, old.evidence)
    new_eval = evaluate_hypotheses(new.hypotheses, new.evidence)
    return {
        "old_version": old.version,
        "new_version": new.version,
        "old_fingerprint": old.fingerprint,
        "new_fingerprint": new.fingerprint,
        "added_hypotheses": tuple(sorted(new_h.keys() - old_h.keys())),
        "removed_hypotheses": tuple(sorted(old_h.keys() - new_h.keys())),
        "revised_hypotheses": tuple(sorted(
            k for k in old_h.keys() & new_h.keys() if old_h[k] != new_h[k])),
        "added_evidence": tuple(sorted(new_e.keys() - old_e.keys())),
        "removed_evidence": tuple(sorted(old_e.keys() - new_e.keys())),
        "revised_evidence": changed,
        "old_evaluation": old_eval["results"],
        "new_evaluation": new_eval["results"],
        "warning": "Evidence stances are human-supplied; counts are not probabilities.",
    }
