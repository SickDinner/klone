"""Portable, canonical HMAC checkpoints for a *trusted* research-ledger snapshot.

Checkpoint verification is meaningful only when the HMAC key is protected
outside the SQLite database. This module does not manage keys or authenticate
callers. It intentionally does not write to the ledger.
"""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
import hashlib
import hmac
import json
from pathlib import Path
import sqlite3


@dataclass(frozen=True)
class LedgerCheckpoint:
    format_version: int
    row_count: int
    snapshot_sha256: str
    signature: str


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


def _snapshot(path: Path) -> tuple[int, str]:
    """Capture both tables in one consistent SQLite read transaction."""
    with closing(sqlite3.connect(Path(path))) as db:
        db.execute("BEGIN")
        claims = db.execute(
            "SELECT claim_id,revision,proposal_id,trace_id,report_version,"
            "statement,source_refs_json,status,rationale "
            "FROM atomic_claims ORDER BY claim_id,revision"
        ).fetchall()
        audits = db.execute(
            "SELECT proposal_id,claim_id,revision,reviewer_id,decision_reason,"
            "audit_digest,created_at FROM atomic_claim_audit ORDER BY proposal_id"
        ).fetchall()
    digest = hashlib.sha256(_canonical_bytes(
        {"format_version": 1, "claims": claims, "audits": audits}
    )).hexdigest()
    return len(claims) + len(audits), digest


def _validate_key(key: bytes) -> None:
    if not isinstance(key, bytes) or len(key) < 32:
        raise ValueError("HMAC key must be at least 32 bytes")


def make_checkpoint(*, database_path: Path, key: bytes) -> LedgerCheckpoint:
    """Sign a read-only snapshot with a secret supplied by a trusted caller."""
    _validate_key(key)
    count, digest = _snapshot(database_path)
    body = [1, count, digest]
    signature = hmac.new(key, _canonical_bytes(body), hashlib.sha256).hexdigest()
    return LedgerCheckpoint(1, count, digest, signature)


def verify_checkpoint(
    *, database_path: Path, checkpoint: LedgerCheckpoint, key: bytes,
) -> bool:
    """Compare signed checkpoint to a fresh snapshot; fail closed."""
    _validate_key(key)
    if not isinstance(checkpoint, LedgerCheckpoint):
        return False
    if checkpoint.format_version != 1:
        return False
    count, digest = _snapshot(database_path)
    body = [checkpoint.format_version, checkpoint.row_count,
            checkpoint.snapshot_sha256]
    expected = hmac.new(key, _canonical_bytes(body), hashlib.sha256).hexdigest()
    return (
        hmac.compare_digest(expected, checkpoint.signature)
        and count == checkpoint.row_count
        and hmac.compare_digest(digest, checkpoint.snapshot_sha256)
    )
