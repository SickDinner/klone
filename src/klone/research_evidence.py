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


class EvidenceLedger:
    """Local public-data claim revisions. Caller enforces identity and permissions.

    A status is a review label, never an automated proof of truth.
    """

    STATUSES = frozenset({"unverified", "supported", "contested", "retracted"})

    def __init__(self, database_path: Path):
        self.database_path = Path(database_path)

    @staticmethod
    def _digest(claim_id: str, revision: int, statement: str,
                refs: tuple[str, ...], status: str, reason: str) -> str:
        payload = json.dumps([claim_id, revision, statement, list(refs), status, reason],
                             ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def _initialize(self, connection: sqlite3.Connection) -> None:
        connection.execute("""CREATE TABLE IF NOT EXISTS research_claim_revisions (
            claim_id TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision > 0),
            statement TEXT NOT NULL, source_refs_json TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('unverified','supported','contested','retracted')),
            reason TEXT NOT NULL, digest TEXT NOT NULL, created_at TEXT NOT NULL,
            PRIMARY KEY (claim_id, revision))""")

    def append(self, *, claim_id: str, statement: str, source_refs: tuple[str, ...],
               status: str = "unverified", reason: str = "") -> EvidenceClaim:
        if not isinstance(claim_id, str) or not 1 <= len(claim_id) <= 128:
            raise ValueError("Invalid claim identifier")
        if not isinstance(statement, str) or not 1 <= len(statement) <= 4000:
            raise ValueError("Invalid statement")
        if (not isinstance(source_refs, tuple) or len(source_refs) > 50 or
            any(not isinstance(ref, str) or not 1 <= len(ref) <= 512 for ref in source_refs)):
            raise ValueError("Invalid source references")
        if status not in self.STATUSES or not isinstance(reason, str) or len(reason) > 2000:
            raise ValueError("Invalid review status or reason")
        if status != "unverified" and (not source_refs or not reason.strip()):
            raise ValueError("Reviewed status requires sources and reason")
        timestamp = datetime.now(timezone.utc).isoformat()
        with closing(sqlite3.connect(self.database_path, timeout=10)) as connection:
            self._initialize(connection)
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                revision = connection.execute(
                    "SELECT COALESCE(MAX(revision), 0) + 1 FROM research_claim_revisions WHERE claim_id = ?",
                    (claim_id,)).fetchone()[0]
                digest = self._digest(claim_id, revision, statement, source_refs, status, reason)
                connection.execute("""INSERT INTO research_claim_revisions
                    (claim_id, revision, statement, source_refs_json, status, reason, digest, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (claim_id, revision, statement, json.dumps(source_refs), status, reason,
                     digest, timestamp))
        return EvidenceClaim(claim_id, revision, statement, source_refs,
                             status, reason, digest, timestamp)

    def history(self, claim_id: str, *, limit: int = 100) -> tuple[EvidenceClaim, ...]:
        if not isinstance(claim_id, str) or not 1 <= len(claim_id) <= 128:
            raise ValueError("Invalid claim identifier")
        if not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("Invalid limit")
        with closing(sqlite3.connect(self.database_path, timeout=10)) as connection:
            self._initialize(connection)
            rows = connection.execute("""SELECT claim_id, revision, statement, source_refs_json,
                status, reason, digest, created_at FROM research_claim_revisions
                WHERE claim_id = ? ORDER BY revision DESC LIMIT ?""", (claim_id, limit)).fetchall()
        records = []
        for row in rows:
            refs = tuple(json.loads(row[3]))
            expected = self._digest(row[0], row[1], row[2], refs, row[4], row[5])
            if expected != row[6]:
                raise ValueError("Claim revision integrity check failed")
            records.append(EvidenceClaim(row[0], row[1], row[2], refs,
                                         row[4], row[5], row[6], row[7]))
        return tuple(records)
