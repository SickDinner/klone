"""Offline one-use assertion replay guard.

Use a durable store for multi-process deployments. This component does not
authenticate an issuer or expose an HTTP endpoint.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import sqlite3

from .approval_identity import SignedActorAssertion, verify_actor_assertion
from .approval_access import VerifiedActor


class AssertionReplayGuard:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS approval_used_assertions ("
            "assertion_sha256 TEXT PRIMARY KEY, expires_at_epoch INTEGER NOT NULL)"
        )

    def verify_once(
        self, assertion: SignedActorAssertion, *, secret: bytes, now: datetime,
        max_age_seconds: int = 300,
    ) -> VerifiedActor:
        actor = verify_actor_assertion(
            assertion, secret=secret, now=now, max_age_seconds=max_age_seconds,
        )
        digest = sha256(assertion.payload + bytes.fromhex(assertion.signature_hex)).hexdigest()
        expires = int(now.timestamp()) + max_age_seconds
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            # No garbage collection until after successful insert; duplicate
            # claims are rejected even if a caller replays them immediately.
            self.connection.execute(
                "INSERT INTO approval_used_assertions(assertion_sha256,expires_at_epoch) "
                "VALUES (?,?)", (digest, expires),
            )
            self.connection.commit()
        except sqlite3.IntegrityError as error:
            self.connection.rollback()
            raise PermissionError("actor_assertion_replayed") from error
        except BaseException:
            self.connection.rollback()
            raise
        return actor
