"""Atomic dossier append + run completion in a single local SQLite database.

Trusted callers must authenticate and authorize the database and run identity.
The 'started' event is a separate durable admission. All dossier writes and
the terminal 'completed' event commit or roll back together. This does not
make external audit callbacks atomic.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
import sqlite3

from .genomics_hypotheses import evaluate_hypotheses
from .research_dossier import build_dossier, compare_dossiers
from .research_dossier_store import DossierStore, _canonical
from .research_dossier_import import import_public_dossier_json
from .research_dossier_review import review_dossier
from .research_source_manifest import PublicSourceManifest
from .research_verified_report import publish_verified_dossier_report
from .research_run_journal import ResearchRunJournal
from .research_audit_outbox import ResearchAuditOutbox
from .integrated_research_core import IntegratedResearchResult
from .research_dossier_workflow import DossierChange


def finalize_verified_run_atomically(
    *, database_path: Path, run_id: str, trace_id: str, dossier_id: str,
    json_text: str, manifests: dict[str, PublicSourceManifest],
    source_bytes: dict[str, bytes],
) -> IntegratedResearchResult:
    """Require an existing started run and atomically save dossier+completion.

    The source bytes are checked before BEGIN IMMEDIATE; caller must supply
    immutable, trusted input. Duplicate/replayed runs fail without a write.
    """
    if (not isinstance(run_id, str) or not 1 <= len(run_id) <= 128 or not run_id.strip()
            or not isinstance(trace_id, str) or not 1 <= len(trace_id) <= 128
            or not trace_id.strip() or not isinstance(dossier_id, str)
            or not 1 <= len(dossier_id) <= 128 or not dossier_id.strip()):
        raise ValueError("Invalid run identity")
    dossier = import_public_dossier_json(json_text)
    if not isinstance(manifests, dict) or not isinstance(source_bytes, dict):
        raise ValueError("Invalid sources")
    frozen_manifests = dict(manifests)
    frozen_bytes = dict(source_bytes)
    if not all(isinstance(k, str) and type(v) is bytes for k, v in frozen_bytes.items()):
        raise ValueError("Invalid source bytes")
    report = publish_verified_dossier_report(
        dossier=dossier, manifests=frozen_manifests, source_bytes=frozen_bytes)
    review = review_dossier(dossier)
    canonical = _canonical(dossier.hypotheses, dossier.evidence)
    with closing(sqlite3.connect(database_path, timeout=10)) as db:
        store = DossierStore(database_path)
        store._initialize(db)
        ResearchRunJournal._schema(db)
        ResearchAuditOutbox.initialize(db)
        db.commit()
        db.execute("BEGIN IMMEDIATE")
        try:
            last = db.execute(
                "SELECT sequence,state,trace_id,dossier_id FROM research_run_journal "
                "WHERE run_id=? ORDER BY sequence DESC LIMIT 1",
                (run_id,)).fetchone()
            if last != (1, "started", trace_id, dossier_id):
                raise ValueError("Run is not in its initial started state")
            version = db.execute(
                "SELECT COALESCE(MAX(version),0)+1 FROM research_dossier_snapshots "
                "WHERE dossier_id=?", (dossier_id,)).fetchone()[0]
            previous = None
            if version > 1:
                row = db.execute(
                    "SELECT canonical_json,fingerprint FROM research_dossier_snapshots "
                    "WHERE dossier_id=? AND version=?",
                    (dossier_id, version - 1)).fetchone()
                if row is None:
                    raise ValueError("Previous dossier missing")
                import json
                from .genomics_hypotheses import Hypothesis, EvidenceItem
                payload = json.loads(row[0])
                old_h = tuple(Hypothesis(**x) for x in payload["hypotheses"])
                old_e = tuple(EvidenceItem(**x) for x in payload["evidence"])
                old = build_dossier(version=version-1, hypotheses=old_h, evidence=old_e)
                if old.fingerprint != row[1] or _canonical(old_h, old_e) != row[0]:
                    raise ValueError("Previous dossier integrity mismatch")
                current = build_dossier(
                    version=version, hypotheses=dossier.hypotheses,
                    evidence=dossier.evidence)
                previous = compare_dossiers(old, current)
            db.execute("INSERT INTO research_dossier_snapshots VALUES (?,?,?,?)",
                       (dossier_id, version, canonical, dossier.fingerprint))
            db.execute("INSERT INTO research_run_journal VALUES (?,?,?,?,?,?)",
                       (run_id, 2, "completed", trace_id, dossier_id,
                        "dossier_version=" + str(version)))
            ResearchAuditOutbox.enqueue_in_transaction(
                db, run_id=run_id, trace_id=trace_id,
                dossier_id=dossier_id, dossier_version=version)
            db.commit()
        except Exception:
            db.rollback()
            raise
    change = DossierChange(dossier_id, version, version - 1 if version > 1 else None,
                           previous)
    return IntegratedResearchResult(change=change, review=review, report=report)
