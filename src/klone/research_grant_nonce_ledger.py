"""One-time signed research grant nonce claims in a trusted local SQLite DB.

This primitive is NOT a complete authorization boundary: the trusted caller
must authenticate principal, check live policy, and commit its protected action
in the same transaction as a nonce claim (or use an idempotent outbox).
"""
from __future__ import annotations

from pathlib import Path
from contextlib import closing
import sqlite3

from .research_signed_grants import SignedResearchGrant, verify_research_grant


def claim_research_grant_nonce(
    *, database_path: Path, grant: SignedResearchGrant, principal: str,
    resource_id: str, report_version: int, policy_version: int,
    now: int, key: bytes,
) -> bool:
    """Claim once, atomically across concurrent SQLite connections.

    Caller owns database_path. A claimed nonce is not released on failure
    of a separate downstream operation, so use with an idempotent workflow.
    """
    if not verify_research_grant(
        grant=grant, principal=principal, resource_id=resource_id,
        report_version=report_version, policy_version=policy_version,
        now=now, key=key,
    ):
        return False
    with closing(sqlite3.connect(database_path, timeout=10)) as db, db:
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            "CREATE TABLE IF NOT EXISTS research_grant_nonces "
            "(nonce TEXT PRIMARY KEY, principal TEXT NOT NULL, "
            "resource_id TEXT NOT NULL, claimed_at INTEGER NOT NULL)"
        )
        try:
            db.execute(
                "INSERT INTO research_grant_nonces "
                "(nonce, principal, resource_id, claimed_at) VALUES (?, ?, ?, ?)",
                (grant.nonce, principal, resource_id, now),
            )
        except sqlite3.IntegrityError:
            db.rollback()
            return False
        db.commit()
        return True
