from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

from .research_report import ResearchReport


@dataclass(frozen=True)
class StoredResearchReport:
    trace_id: str
    version: int
    room_id: str
    title: str
    markdown: str
    citations: tuple[str, ...]
    content_sha256: str
    created_at: str


class ResearchMemory:
    """Append-only, public-data-only research report history.

    This class does not authenticate callers. Do not expose it as a public API.
    """

    def __init__(self, database_path: Path):
        self.database_path = Path(database_path)

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.execute("PRAGMA busy_timeout=10000")
        connection.execute("""
            CREATE TABLE IF NOT EXISTS research_report_versions (
                trace_id TEXT NOT NULL,
                version INTEGER NOT NULL CHECK(version > 0),
                room_id TEXT NOT NULL CHECK(room_id = 'public-room'),
                title TEXT NOT NULL,
                markdown TEXT NOT NULL,
                citations_json TEXT NOT NULL,
                content_sha256 TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY(trace_id, version)
            )
        """)
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _digest(report: ResearchReport) -> str:
        payload = json.dumps(
            [report.trace_id, report.room_id, report.title,
             report.markdown, list(report.citations)],
            ensure_ascii=False, separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def save(self, report: ResearchReport) -> StoredResearchReport:
        if report.room_id != "public-room":
            raise ValueError("Research memory preview accepts public-room only")
        if not report.trace_id or not report.title or not report.markdown:
            raise ValueError("Incomplete research report")
        if not all(isinstance(c, str) for c in report.citations):
            raise ValueError("Invalid citations")
        digest = self._digest(report)
        timestamp = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            version = connection.execute(
                "SELECT COALESCE(MAX(version), 0) + 1 FROM research_report_versions WHERE trace_id = ?",
                (report.trace_id,),
            ).fetchone()[0]
            connection.execute(
                """INSERT INTO research_report_versions
                (trace_id, version, room_id, title, markdown, citations_json, content_sha256, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (report.trace_id, version, report.room_id, report.title,
                 report.markdown, json.dumps(list(report.citations)),
                 digest, timestamp),
            )
        return StoredResearchReport(report.trace_id, version, report.room_id,
                                    report.title, report.markdown,
                                    report.citations, digest, timestamp)

    def read(self, *, trace_id: str, version: int | None = None) -> StoredResearchReport | None:
        if not trace_id or (version is not None and version < 1):
            raise ValueError("Invalid report identifier")
        with self._connect() as connection:
            if version is None:
                row = connection.execute(
                    """SELECT trace_id, version, room_id, title, markdown,
                       citations_json, content_sha256, created_at
                       FROM research_report_versions WHERE trace_id = ?
                       ORDER BY version DESC LIMIT 1""", (trace_id,),
                ).fetchone()
            else:
                row = connection.execute(
                    """SELECT trace_id, version, room_id, title, markdown,
                       citations_json, content_sha256, created_at
                       FROM research_report_versions WHERE trace_id = ? AND version = ?""",
                    (trace_id, version),
                ).fetchone()
        if row is None:
            return None
        record = StoredResearchReport(row[0], row[1], row[2], row[3],
                                      row[4], tuple(json.loads(row[5])),
                                      row[6], row[7])
        if self._digest(ResearchReport(record.trace_id, record.room_id,
                                     record.title, record.markdown,
                                     record.citations)) != record.content_sha256:
            raise ValueError("Research report integrity check failed")
        return record
