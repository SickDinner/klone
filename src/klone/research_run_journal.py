"""Durable append-only run journal for KLONE local research operations.

Records immutable state transitions in a local SQLite database. Does not
authenticate users or imply atomicity with a separate dossier database.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
import sqlite3


_STATES = {"started", "completed", "failed"}
_ALLOWED = {None: {"started"}, "started": {"completed", "failed"},
            "completed": set(), "failed": set()}


@dataclass(frozen=True)
class RunEvent:
    run_id: str
    sequence: int
    state: str
    trace_id: str
    dossier_id: str
    detail: str


class ResearchRunJournal:
    def __init__(self, database_path: Path):
        self.database_path = Path(database_path)

    @staticmethod
    def _schema(db: sqlite3.Connection) -> None:
        db.execute("""CREATE TABLE IF NOT EXISTS research_run_journal (
            run_id TEXT NOT NULL,
            sequence INTEGER NOT NULL,
            state TEXT NOT NULL CHECK(state IN ('started','completed','failed')),
            trace_id TEXT NOT NULL,
            dossier_id TEXT NOT NULL,
            detail TEXT NOT NULL,
            PRIMARY KEY(run_id,sequence))""")

    def transition(
        self, *, run_id: str, state: str, trace_id: str,
        dossier_id: str, detail: str = "",
    ) -> RunEvent:
        if (not isinstance(run_id, str) or not 1 <= len(run_id) <= 128
                or not run_id.strip() or state not in _STATES
                or not isinstance(trace_id, str) or not 1 <= len(trace_id) <= 128
                or not trace_id.strip() or not isinstance(dossier_id, str)
                or not 1 <= len(dossier_id) <= 128 or not dossier_id.strip()
                or not isinstance(detail, str) or len(detail) > 1000):
            raise ValueError("Invalid run event")
        with closing(sqlite3.connect(self.database_path, timeout=10)) as db:
            self._schema(db)
            db.commit()
            db.execute("BEGIN IMMEDIATE")
            try:
                last = db.execute(
                    "SELECT sequence,state,trace_id,dossier_id FROM research_run_journal "
                    "WHERE run_id=? ORDER BY sequence DESC LIMIT 1",
                    (run_id,)).fetchone()
                previous = last[1] if last else None
                if state not in _ALLOWED[previous]:
                    raise ValueError("Invalid run state transition")
                if last and (last[2] != trace_id or last[3] != dossier_id):
                    raise ValueError("Run identity changed")
                sequence = (last[0] + 1) if last else 1
                db.execute("INSERT INTO research_run_journal VALUES (?,?,?,?,?,?)",
                           (run_id, sequence, state, trace_id, dossier_id, detail))
                db.commit()
            except Exception:
                db.rollback()
                raise
        return RunEvent(run_id, sequence, state, trace_id, dossier_id, detail)

    def history(self, *, run_id: str) -> tuple[RunEvent, ...]:
        if not isinstance(run_id, str) or not run_id.strip():
            raise ValueError("Invalid run id")
        with closing(sqlite3.connect(self.database_path, timeout=10)) as db:
            self._schema(db)
            rows = db.execute(
                "SELECT run_id,sequence,state,trace_id,dossier_id,detail "
                "FROM research_run_journal WHERE run_id=? ORDER BY sequence",
                (run_id,)).fetchall()
        return tuple(RunEvent(*row) for row in rows)
