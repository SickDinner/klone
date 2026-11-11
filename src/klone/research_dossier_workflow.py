"""Small, explicit public dossier workflow over versioned SQLite snapshots.

Caller must authenticate, authorize database path, and vet source references.
No source retrieval or model inference occurs here.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .genomics_hypotheses import EvidenceItem, Hypothesis
from .research_dossier import build_dossier, compare_dossiers
from .research_dossier_store import DossierStore


@dataclass(frozen=True)
class DossierChange:
    dossier_id: str
    version: int
    previous_version: int | None
    changes: dict[str, object] | None


def append_research_dossier(
    *, database_path: Path, dossier_id: str,
    hypotheses: tuple[Hypothesis, ...], evidence: tuple[EvidenceItem, ...],
) -> DossierChange:
    """Persist a validated version and compare with its immediate predecessor.

    On failure after append, the new version remains committed. The caller
    can retry reading by version, not assume rollback across these operations.
    """
    store = DossierStore(database_path)
    version = store.append(dossier_id=dossier_id, hypotheses=hypotheses,
                           evidence=evidence)
    if version == 1:
        return DossierChange(dossier_id, version, None, None)
    previous_h, previous_e = store.read(dossier_id=dossier_id, version=version - 1)
    old = build_dossier(version=version - 1, hypotheses=previous_h, evidence=previous_e)
    new = build_dossier(version=version, hypotheses=hypotheses, evidence=evidence)
    return DossierChange(dossier_id, version, version - 1,
                         compare_dossiers(old, new))


def read_research_dossier(
    *, database_path: Path, dossier_id: str, version: int,
):
    """Return a fingerprint-verified version; does not grant access rights."""
    hypotheses, evidence = DossierStore(database_path).read(
        dossier_id=dossier_id, version=version)
    return build_dossier(version=version, hypotheses=hypotheses, evidence=evidence)
