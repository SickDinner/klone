from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from contextlib import closing


@dataclass(frozen=True)
class EvidenceClaim:
    claim_id: str
    revision: int
    statement: str
    source_refs: tuple[str, ...]
    status: str
    reason: str
    digest: str
    created_at: str
    report_trace_id: str | None = None
    report_version: int | None = None


class EvidenceLedger:
    """Local public-data claim revisions. Caller enforces identity and permissions.

    A status is a review label, never an automated proof of truth.
    """

    STATUSES = frozenset({"unverified", "supported", "contested", "retracted"})

    def __init__(self, database_path: Path):
        self.database_path = Path(database_path)

    @staticmethod
    def _digest(claim_id: str, revision: int, statement: str,
                refs: tuple[str, ...], status: str, reason: str,
                report_trace_id: str | None = None,
                report_version: int | None = None) -> str:
        payload = json.dumps([claim_id, revision, statement, list(refs), status, reason, report_trace_id, report_version],
                             ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def _initialize(self, connection: sqlite3.Connection) -> None:
        connection.execute("""CREATE TABLE IF NOT EXISTS research_claim_revisions (
            claim_id TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision > 0),
            statement TEXT NOT NULL, source_refs_json TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('unverified','supported','contested','retracted')),
            reason TEXT NOT NULL, digest TEXT NOT NULL, created_at TEXT NOT NULL,
            report_trace_id TEXT, report_version INTEGER,
            PRIMARY KEY (claim_id, revision))""")

    def append(self, *, claim_id: str, statement: str, source_refs: tuple[str, ...],
               status: str = "unverified", reason: str = "",
               report_trace_id: str | None = None,
               report_version: int | None = None) -> EvidenceClaim:
        if not isinstance(claim_id, str) or not 1 <= len(claim_id) <= 128:
            raise ValueError("Invalid claim identifier")
        if not isinstance(statement, str) or not 1 <= len(statement) <= 4000:
            raise ValueError("Invalid statement")
        if (not isinstance(source_refs, tuple) or len(source_refs) > 50 or
            any(not isinstance(ref, str) or not 1 <= len(ref) <= 512 for ref in source_refs)):
            raise ValueError("Invalid source references")
        if not isinstance(status, str) or status not in self.STATUSES or not isinstance(reason, str) or len(reason) > 2000:
            raise ValueError("Invalid review status or reason")
        if status != "unverified" and (not source_refs or not reason.strip()):
            raise ValueError("Reviewed status requires sources and reason")
        if (report_trace_id is None) != (report_version is None):
            raise ValueError("Report trace and version must be provided together")
        if report_trace_id is not None and (
            not isinstance(report_trace_id, str) or not 1 <= len(report_trace_id) <= 128
            or type(report_version) is not int or report_version < 1
        ):
            raise ValueError("Invalid report provenance")
        timestamp = datetime.now(timezone.utc).isoformat()
        with closing(sqlite3.connect(self.database_path, timeout=10)) as connection:
            self._initialize(connection)
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                revision = connection.execute(
                    "SELECT COALESCE(MAX(revision), 0) + 1 FROM research_claim_revisions WHERE claim_id = ?",
                    (claim_id,)).fetchone()[0]
                digest = self._digest(claim_id, revision, statement, source_refs, status, reason,
                                      report_trace_id, report_version)
                connection.execute("""INSERT INTO research_claim_revisions
                    (claim_id, revision, statement, source_refs_json, status, reason, digest, created_at, report_trace_id, report_version)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (claim_id, revision, statement, json.dumps(source_refs), status, reason,
                     digest, timestamp, report_trace_id, report_version))
        return EvidenceClaim(claim_id, revision, statement, source_refs,
                             status, reason, digest, timestamp, report_trace_id, report_version)

    def append_from_report(
        self, *, memory, trace_id: str, version: int, claim_id: str,
        statement: str, source_refs: tuple[str, ...],
        status: str = "unverified", reason: str = "",
    ) -> EvidenceClaim:
        """Bind a claim revision to verified citations of a stored public report.

        This validates provenance membership only; not whether sources prove a claim.
        Caller must authorize report and ledger access and record an audit event.
        """
        if type(version) is not int or version < 1:
            raise ValueError("Invalid report version")
        report = memory.read(trace_id=trace_id, version=version)
        if report is None or report.room_id != "public-room":
            raise ValueError("Public report version not found")
        if (not isinstance(source_refs, tuple) or not source_refs or
            any(not isinstance(ref, str) or ref not in report.citations for ref in source_refs)):
            raise ValueError("Claim references must belong to the stored report")
        return self.append(
            claim_id=claim_id, statement=statement, source_refs=source_refs,
            status=status, reason=reason,
            report_trace_id=trace_id, report_version=version,
        )

    def history(self, claim_id: str, *, limit: int = 100) -> tuple[EvidenceClaim, ...]:
        if not isinstance(claim_id, str) or not 1 <= len(claim_id) <= 128:
            raise ValueError("Invalid claim identifier")
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("Invalid limit")
        with closing(sqlite3.connect(self.database_path, timeout=10)) as connection:
            self._initialize(connection)
            rows = connection.execute("""SELECT claim_id, revision, statement, source_refs_json,
                status, reason, digest, created_at, report_trace_id, report_version FROM research_claim_revisions
                WHERE claim_id = ? ORDER BY revision DESC LIMIT ?""", (claim_id, limit)).fetchall()
        records = []
        for row in rows:
            refs = tuple(json.loads(row[3]))
            expected = self._digest(row[0], row[1], row[2], refs, row[4], row[5], row[8], row[9])
            if expected != row[6]:
                raise ValueError("Claim revision integrity check failed")
            records.append(EvidenceClaim(row[0], row[1], row[2], refs,
                                         row[4], row[5], row[6], row[7], row[8], row[9]))
        return tuple(records)
