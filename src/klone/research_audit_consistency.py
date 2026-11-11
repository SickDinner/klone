"""Read-only integrity checks for KLONE research run/outbox consistency.

No automatic repairs, no writes, and no exposure of raw dossier contents.
Trusted host must authorize the database and presentation of identifiers.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
import sqlite3


@dataclass(frozen=True)
class AuditConsistency:
    completed_missing_snapshot: tuple[str, ...]
    outbox_missing_completed: tuple[str, ...]
    outbox_version_mismatch: tuple[str, ...]
    malformed_event_ids: tuple[str, ...]

    @property
    def healthy(self) -> bool:
        return not (self.completed_missing_snapshot or
                    self.outbox_missing_completed or
                    self.outbox_version_mismatch or
                    self.malformed_event_ids)


def inspect_audit_consistency(*, database_path: Path) -> AuditConsistency:
    path = Path(database_path)
    if not path.is_file():
        raise FileNotFoundError("Research database does not exist")
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        tables = {x[0] for x in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"research_run_journal", "research_audit_outbox",
                "research_dossier_snapshots"}.issubset(tables):
            raise ValueError("Research integrity schema incomplete")
        missing_snapshot = db.execute(
            "SELECT j.run_id FROM research_run_journal j "
            "WHERE j.state='completed' AND NOT EXISTS ("
            "SELECT 1 FROM research_audit_outbox o "
            "JOIN research_dossier_snapshots d "
            "ON d.dossier_id=o.dossier_id AND d.version=o.dossier_version "
            "WHERE o.run_id=j.run_id AND o.dossier_id=j.dossier_id "
            "AND o.trace_id=j.trace_id) ORDER BY j.run_id").fetchall()
        missing_completed = db.execute(
            "SELECT o.event_id FROM research_audit_outbox o "
            "WHERE NOT EXISTS (SELECT 1 FROM research_run_journal j "
            "WHERE j.run_id=o.run_id AND j.state='completed' "
            "AND j.dossier_id=o.dossier_id AND j.trace_id=o.trace_id) "
            "ORDER BY o.event_id").fetchall()
        mismatch = db.execute(
            "SELECT o.event_id FROM research_audit_outbox o "
            "WHERE NOT EXISTS (SELECT 1 FROM research_dossier_snapshots d "
            "WHERE d.dossier_id=o.dossier_id AND d.version=o.dossier_version) "
            "ORDER BY o.event_id").fetchall()
        bad_ids = db.execute(
            "SELECT event_id FROM research_audit_outbox "
            "WHERE event_id != ('research-run:' || run_id) "
            "ORDER BY event_id").fetchall()
    return AuditConsistency(
        completed_missing_snapshot=tuple(x[0] for x in missing_snapshot),
        outbox_missing_completed=tuple(x[0] for x in missing_completed),
        outbox_version_mismatch=tuple(x[0] for x in mismatch),
        malformed_event_ids=tuple(x[0] for x in bad_ids))
