"""Durable, retryable SQLite audit outbox for completed KLONE research runs.

This is an at-least-once delivery mechanism, not exactly-once delivery.
Consumers MUST deduplicate by event_id. The caller authenticates and
authorizes database access and the external audit sink.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import Callable


@dataclass(frozen=True)
class OutboxEvent:
    event_id: str
    run_id: str
    trace_id: str
    dossier_id: str
    dossier_version: int
    delivered: bool


class ResearchAuditOutbox:
    def __init__(self, database_path: Path):
        self.database_path = Path(database_path)

    @staticmethod
    def initialize(db: sqlite3.Connection) -> None:
        db.execute("""CREATE TABLE IF NOT EXISTS research_audit_outbox (
            event_id TEXT PRIMARY KEY, run_id TEXT NOT NULL UNIQUE,
            trace_id TEXT NOT NULL, dossier_id TEXT NOT NULL,
            dossier_version INTEGER NOT NULL CHECK(dossier_version > 0),
            delivered INTEGER NOT NULL DEFAULT 0 CHECK(delivered IN (0,1)))""")

    @staticmethod
    def enqueue_in_transaction(
        db: sqlite3.Connection, *, run_id: str, trace_id: str,
        dossier_id: str, dossier_version: int,
    ) -> str:
        """Must be called INSIDE the dossier+completion SQLite transaction."""
        if not db.in_transaction:
            raise RuntimeError("Outbox requires active SQLite transaction")
        if (not isinstance(run_id, str) or not 1 <= len(run_id) <= 128
                or not run_id.strip() or not isinstance(trace_id, str)
                or not trace_id.strip() or not isinstance(dossier_id, str)
                or not dossier_id.strip() or type(dossier_version) is not int
                or dossier_version < 1):
            raise ValueError("Invalid outbox event")
        event_id = "research-run:" + run_id
        db.execute(
            "INSERT INTO research_audit_outbox "
            "(event_id,run_id,trace_id,dossier_id,dossier_version) "
            "VALUES (?,?,?,?,?)",
            (event_id, run_id, trace_id, dossier_id, dossier_version))
        return event_id

    def pending(self, *, limit: int = 100) -> tuple[OutboxEvent, ...]:
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("Invalid outbox limit")
        with closing(sqlite3.connect(self.database_path, timeout=10)) as db:
            self.initialize(db)
            rows = db.execute(
                "SELECT event_id,run_id,trace_id,dossier_id,dossier_version,delivered "
                "FROM research_audit_outbox WHERE delivered=0 ORDER BY rowid LIMIT ?",
                (limit,)).fetchall()
        return tuple(OutboxEvent(*row) for row in rows)

    def deliver(self, *, sink: Callable[[OutboxEvent], None],
                limit: int = 100) -> int:
        """Deliver pending events; sink must deduplicate by event_id.

        A crash after sink success but before ack can cause redelivery.
        """
        if not callable(sink):
            raise ValueError("Audit sink required")
        sent = 0
        for event in self.pending(limit=limit):
            sink(event)
            with closing(sqlite3.connect(self.database_path, timeout=10)) as db:
                db.execute("BEGIN IMMEDIATE")
                try:
                    db.execute(
                        "UPDATE research_audit_outbox SET delivered=1 "
                        "WHERE event_id=? AND delivered=0", (event.event_id,))
                    db.commit()
                except Exception:
                    db.rollback()
                    raise
            sent += 1
        return sent
