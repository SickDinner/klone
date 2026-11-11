"""KLONE 4.0 first integrated, local-only public research workflow.

Caller authenticates and authorizes the database path and supplies curated
public evidence plus source bytes. No network access, private genetics, agent
autonomy, or claim-publication authority is implied.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .research_dossier_import import import_public_dossier_json
from .research_dossier_workflow import append_research_dossier, read_research_dossier, DossierChange
from .research_dossier_review import review_dossier, DossierReview
from .research_verified_report import publish_verified_dossier_report, GatedReport
from .research_source_manifest import PublicSourceManifest


@dataclass(frozen=True)
class IntegratedResearchResult:
    change: DossierChange
    review: DossierReview
    report: GatedReport


def run_integrated_public_research(
    *, database_path: Path, dossier_id: str, json_text: str,
    manifests: dict[str, PublicSourceManifest],
    source_bytes: dict[str, bytes],
) -> IntegratedResearchResult:
    """Verify all supplied source bytes BEFORE writing a dossier version.

    The saved dossier is re-read after commit and re-verified against sources.
    Failures after commit cannot undo the saved append-only dossier version.
    This is a curated local workflow, not autonomous source discovery.
    """
    imported = import_public_dossier_json(json_text)
    # Freeze source input to avoid mutation by a caller during this operation.
    if not isinstance(source_bytes, dict) or not all(
        isinstance(k, str) and type(v) is bytes for k, v in source_bytes.items()
    ):
        raise ValueError("Invalid source bytes")
    frozen_bytes = dict(source_bytes)
    frozen_manifests = dict(manifests) if isinstance(manifests, dict) else None
    if frozen_manifests is None:
        raise ValueError("Invalid source manifests")
    publish_verified_dossier_report(
        dossier=imported, manifests=frozen_manifests, source_bytes=frozen_bytes)
    # Review also occurs before the first write.
    review_dossier(imported)
    change = append_research_dossier(
        database_path=database_path, dossier_id=dossier_id,
        hypotheses=imported.hypotheses, evidence=imported.evidence)
    persisted = read_research_dossier(
        database_path=database_path, dossier_id=dossier_id,
        version=change.version)
    if persisted.fingerprint != imported.fingerprint:
        raise ValueError("Persisted dossier fingerprint mismatch")
    report = publish_verified_dossier_report(
        dossier=persisted, manifests=frozen_manifests, source_bytes=frozen_bytes)
    return IntegratedResearchResult(
        change=change, review=review_dossier(persisted), report=report)
