"""Read-only operator diagnostics for interrupted KLONE research runs.

This module never retries a run, modifies a database, or assumes that
an unfinished 'started' event is safe to resume.
Trusted host MUST authorize the requested database and dossier.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
import sqlite3


@dataclass(frozen=True)
class ResearchRecoveryStatus:
    started_without_terminal: tuple[str, ...]
    completed_without_outbox: tuple[str, ...]
    pending_audit_delivery: tuple[str, ...]


def inspect_research_recovery(*, database_path: Path) -> ResearchRecoveryStatus:
    path = Path(database_path)
    if not path.is_file():
        raise FileNotFoundError("Research database does not exist")
    # Read-only URI ensures diagnostics cannot create or change database files.
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        needed = {"research_run_journal", "research_audit_outbox"}
        present = {row[0] for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if not needed.issubset(present):
            raise ValueError("Research recovery schema incomplete")
        started = db.execute(
            "SELECT j.run_id FROM research_run_journal AS j "
            "WHERE j.state='started' AND NOT EXISTS ("
            "SELECT 1 FROM research_run_journal AS terminal "
            "WHERE terminal.run_id=j.run_id AND terminal.state IN ('completed','failed')) "
            "ORDER BY j.run_id").fetchall()
        completed_missing = db.execute(
            "SELECT j.run_id FROM research_run_journal AS j "
            "WHERE j.state='completed' AND NOT EXISTS ("
            "SELECT 1 FROM research_audit_outbox AS o WHERE o.run_id=j.run_id) "
            "ORDER BY j.run_id").fetchall()
        pending = db.execute(
            "SELECT event_id FROM research_audit_outbox WHERE delivered=0 "
            "ORDER BY event_id").fetchall()
    return ResearchRecoveryStatus(
        started_without_terminal=tuple(row[0] for row in started),
        completed_without_outbox=tuple(row[0] for row in completed_missing),
        pending_audit_delivery=tuple(row[0] for row in pending))
