"""Trusted local JSON-to-versioned-dossier pipeline.

The caller must authenticate and authorize the database path. Inputs must be
curated public research metadata; no raw genetic or private records.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .research_dossier_import import import_public_dossier_json
from .research_dossier_workflow import append_research_dossier, DossierChange
from .research_dossier_review import review_dossier, DossierReview
from .research_dossier import build_dossier


@dataclass(frozen=True)
class PipelineResult:
    change: DossierChange
    review: DossierReview


def run_public_dossier_pipeline(
    *, database_path: Path, dossier_id: str, json_text: str,
) -> PipelineResult:
    """Import, persist, and triage public research data in one explicit call.

    Snapshot persistence commits before review. Failures after commit do not
    roll back a saved version; callers should inspect the stored history.
    """
    imported = import_public_dossier_json(json_text)
    change = append_research_dossier(
        database_path=database_path, dossier_id=dossier_id,
        hypotheses=imported.hypotheses, evidence=imported.evidence)
    current = build_dossier(version=change.version, hypotheses=imported.hypotheses,
                            evidence=imported.evidence)
    return PipelineResult(change=change, review=review_dossier(current))
