"""Local append-only test evidence ledger with source separation.

No network access, GitHub token or automatic approval. Writes only to an
explicitly supplied SQLite database path.
"""
from __future__ import annotations

import hashlib
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from datetime import datetime, timezone


SCHEMA_VERSION = 1
SOURCES = frozenset({"github_actions", "termux_bridge"})
STATUSES = frozenset({"success", "failure", "pending", "cancelled"})


def canonical(record: dict) -> str:
    return json.dumps(record, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def validate(record: dict) -> dict:
    required = {"source", "run_id", "commit", "status", "observed_at"}
    if not isinstance(record, dict) or not required.issubset(record):
        raise ValueError("missing evidence fields")
    if record["source"] not in SOURCES or record["status"] not in STATUSES:
        raise ValueError("unsupported evidence source or status")
    for key in ("run_id", "commit", "observed_at"):
        if not isinstance(record[key], str) or not record[key].strip() or len(record[key]) > 200:
            raise ValueError(f"invalid {key}")
    commit = record["commit"]
    if not (7 <= len(commit) <= 40 and all(c in "0123456789abcdef" for c in commit)):
        raise ValueError("commit must be a lowercase hexadecimal Git SHA")
    try:
        timestamp = datetime.fromisoformat(record["observed_at"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid observed_at") from exc
    if timestamp.tzinfo is None:
        raise ValueError("observed_at must have timezone")
    allowed = required | {"environment", "details", "schema_version"}
    if set(record) - allowed:
        raise ValueError("unexpected evidence fields")
    if record.get("schema_version", SCHEMA_VERSION) != SCHEMA_VERSION:
        raise ValueError("unsupported schema version")
    if not isinstance(record.get("environment", ""), str) or len(record.get("environment", "")) > 200:
        raise ValueError("invalid environment")
    details = record.get("details", {})
    if not isinstance(details, dict) or len(canonical(details)) > 8192:
        raise ValueError("invalid details")
    normalized = {**record, "schema_version": SCHEMA_VERSION}
    if len(canonical(normalized)) > 10000:
        raise ValueError("evidence too large")
    return normalized


class EvidenceLedger:
    def __init__(self, database: str | Path):
        self.database = str(database)

    def initialize(self):
        with closing(sqlite3.connect(self.database)) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS test_evidence (
                fingerprint TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                run_id TEXT NOT NULL,
                commit_sha TEXT NOT NULL,
                status TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                inserted_at TEXT NOT NULL
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS idx_evidence_commit ON test_evidence(commit_sha, source)")
            db.commit()

    def append(self, record: dict) -> tuple[str, bool]:
        payload = canonical(validate(record))
        fingerprint = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        now = datetime.now(timezone.utc).isoformat()
        with closing(sqlite3.connect(self.database)) as db:
            existing = db.execute("SELECT payload_json FROM test_evidence WHERE fingerprint=?", (fingerprint,)).fetchone()
            if existing:
                if existing[0] != payload:
                    raise ValueError("evidence fingerprint collision")
                return fingerprint, False
            db.execute("INSERT INTO test_evidence VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                       (fingerprint, record["source"], record["run_id"], record["commit"],
                        record["status"], record["observed_at"], payload, now))
            db.commit()
        return fingerprint, True

    def list_for_commit(self, commit: str) -> list[dict]:
        with closing(sqlite3.connect(self.database)) as db:
            rows = db.execute(
                "SELECT payload_json FROM test_evidence WHERE commit_sha=? ORDER BY observed_at, fingerprint",
                (commit,),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def compare(self, commit: str) -> dict:
        rows = self.list_for_commit(commit)
        sources = {source: [r for r in rows if r["source"] == source] for source in sorted(SOURCES)}
        return {
            "commit": commit,
            "sources": {source: {"count": len(items), "statuses": sorted({r["status"] for r in items})}
                        for source, items in sources.items()},
            "review_state": "manual_review_required" if all(sources.values()) else "pending_evidence",
        }
