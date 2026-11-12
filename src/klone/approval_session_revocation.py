"""Offline SQLite-backed session revocation registry.

The registry is an explicit denylist, not a login/session issuer. Callers
must derive session identifiers from trusted authenticated server context.
"""
from __future__ import annotations

from datetime import datetime
import sqlite3


class SessionRevocationRegistry:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS approval_revoked_sessions ("
            "session_id TEXT PRIMARY KEY, revoked_at_epoch INTEGER NOT NULL,"
            "reason TEXT NOT NULL)"
        )

    @staticmethod
    def _validate(session_id: str) -> None:
        if (not isinstance(session_id, str) or not session_id.strip()
                or len(session_id) > 128):
            raise PermissionError("invalid_session_id")

    def is_revoked(self, session_id: str) -> bool:
        self._validate(session_id)
        return self.connection.execute(
            "SELECT 1 FROM approval_revoked_sessions WHERE session_id=?",
            (session_id,),
        ).fetchone() is not None

    def require_active(self, session_id: str) -> None:
        if self.is_revoked(session_id):
            raise PermissionError("approval_session_revoked")

    def revoke(self, session_id: str, *, now: datetime, reason: str) -> None:
        self._validate(session_id)
        if (not isinstance(now, datetime) or now.tzinfo is None
                or now.utcoffset() is None or not isinstance(reason, str)
                or not reason.strip() or len(reason) > 256):
            raise ValueError("invalid_revocation")
        try:
            self.connection.execute(
                "INSERT INTO approval_revoked_sessions "
                "(session_id, revoked_at_epoch, reason) VALUES (?, ?, ?)",
                (session_id, int(now.timestamp()), reason),
            )
        except sqlite3.IntegrityError as error:
            raise PermissionError("session_already_revoked") from error
