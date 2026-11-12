"""Local approval journal, with atomic state transitions and append-only audit.

No HTTP endpoints, identity provider, or target mutation are provided.
The caller must authenticate the actor and enforce role/room policy.
"""
from __future__ import annotations

from dataclasses import dataclass
import sqlite3
from datetime import datetime, timezone
from typing import Literal

from .approval_policy import ApprovalProposal, advance_proposal

SCHEMA = """
CREATE TABLE IF NOT EXISTS approval_proposals (
 proposal_id TEXT PRIMARY KEY, proposer_id TEXT NOT NULL, room_id TEXT NOT NULL,
 target_version TEXT NOT NULL, patch_sha256 TEXT NOT NULL,
 state TEXT NOT NULL, approver_id TEXT
);
CREATE TABLE IF NOT EXISTS approval_deadlines (
 proposal_id TEXT PRIMARY KEY REFERENCES approval_proposals(proposal_id),
 expires_at_utc TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS approval_revocations (\n proposal_id TEXT PRIMARY KEY REFERENCES approval_proposals(proposal_id),\n revoked_by TEXT NOT NULL, revoked_at_utc TEXT NOT NULL, reason TEXT NOT NULL\n);\nCREATE TABLE IF NOT EXISTS approval_events (
 event_id INTEGER PRIMARY KEY AUTOINCREMENT,
 proposal_id TEXT NOT NULL, actor_id TEXT NOT NULL,
 previous_state TEXT, next_state TEXT NOT NULL,
 FOREIGN KEY(proposal_id) REFERENCES approval_proposals(proposal_id)
);
"""


@dataclass(frozen=True)
class ApprovalEvent:
    proposal_id: str
    actor_id: str
    previous_state: str | None
    next_state: str


class ApprovalJournal:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript(SCHEMA)

    def _begin_write(self) -> bool:
        nested = self.connection.in_transaction
        self.connection.execute("SAVEPOINT approval_journal_write" if nested else "BEGIN IMMEDIATE")
        return nested

    def _finish_write(self, nested: bool, *, success: bool) -> None:
        if nested:
            if not success:
                self.connection.execute("ROLLBACK TO SAVEPOINT approval_journal_write")
            self.connection.execute("RELEASE SAVEPOINT approval_journal_write")
        elif success:
            self.connection.commit()
        else:
            self.connection.rollback()

    def propose(self, proposal: ApprovalProposal, *, actor_id: str, expires_at: datetime | None = None) -> ApprovalProposal:
        if (not actor_id or actor_id != proposal.proposer_id or proposal.state != "proposed"
                or proposal.approver_id is not None or not proposal.proposal_id.strip()
                or not proposal.room_id.strip() or not proposal.target_version.strip()
                or len(proposal.patch_sha256) != 64
                or any(c not in "0123456789abcdef" for c in proposal.patch_sha256)):
            raise ValueError("invalid_proposal")
        if expires_at is not None and (not isinstance(expires_at, datetime) or expires_at.tzinfo is None or expires_at.utcoffset() is None):
            raise ValueError("timezone_aware_expiry_required")
        # Explicit transaction: sqlite3 connection context manager alone does
        # not start a transaction when isolation_level=None (autocommit).
        nested = self._begin_write()
        try:
            self.connection.execute(
                "INSERT INTO approval_proposals VALUES (?, ?, ?, ?, ?, ?, ?)",
                (proposal.proposal_id, proposal.proposer_id, proposal.room_id,
                 proposal.target_version, proposal.patch_sha256, proposal.state, None),
            )
            if expires_at is not None:
                self.connection.execute(
                    "INSERT INTO approval_deadlines(proposal_id,expires_at_utc) VALUES (?,?)",
                    (proposal.proposal_id, expires_at.astimezone(timezone.utc).isoformat()),
                )
            self.connection.execute(
                "INSERT INTO approval_events(proposal_id,actor_id,previous_state,next_state) VALUES (?,?,?,?)",
                (proposal.proposal_id, actor_id, None, "proposed"),
            )
            self._finish_write(nested, success=True)
        except BaseException:
            self._finish_write(nested, success=False)
            raise
        return proposal

    def get(self, proposal_id: str) -> ApprovalProposal | None:
        row = self.connection.execute(
            "SELECT proposal_id,proposer_id,room_id,target_version,patch_sha256,state,approver_id "
            "FROM approval_proposals WHERE proposal_id=?", (proposal_id,),
        ).fetchone()
        return ApprovalProposal(*row) if row else None

    def transition(
        self, proposal_id: str, next_state: str, *, actor_id: str,
        human_approved: bool = False, current_target_version: str | None = None,
        current_patch_sha256: str | None = None,
    ) -> ApprovalProposal:
        # BEGIN IMMEDIATE serializes competing writers and prevents stale reads.
        nested = self._begin_write()
        try:
            proposal = self.get(proposal_id)
            if proposal is None:
                raise ValueError("unknown_proposal")
            updated = advance_proposal(
                proposal, next_state, actor_id=actor_id, human_approved=human_approved,
                current_target_version=current_target_version,
                current_patch_sha256=current_patch_sha256,
            )
            cursor = self.connection.execute(
                "UPDATE approval_proposals SET state=?,approver_id=? "
                "WHERE proposal_id=? AND state=?",
                (updated.state, updated.approver_id, proposal_id, proposal.state),
            )
            if cursor.rowcount != 1:
                raise ValueError("concurrent_transition")
            self.connection.execute(
                "INSERT INTO approval_events(proposal_id,actor_id,previous_state,next_state) VALUES (?,?,?,?)",
                (proposal_id, actor_id, proposal.state, updated.state),
            )
            self._finish_write(nested, success=True)
            return updated
        except BaseException:
            self._finish_write(nested, success=False)
            raise

    def events(self, proposal_id: str) -> tuple[ApprovalEvent, ...]:
        rows = self.connection.execute(
            "SELECT proposal_id,actor_id,previous_state,next_state FROM approval_events "
            "WHERE proposal_id=? ORDER BY event_id", (proposal_id,),
        ).fetchall()
        return tuple(ApprovalEvent(*row) for row in rows)

    def deadline(self, proposal_id: str) -> datetime | None:
        row = self.connection.execute(
            "SELECT expires_at_utc FROM approval_deadlines WHERE proposal_id=?", (proposal_id,),
        ).fetchone()
        return datetime.fromisoformat(row[0]) if row else None

    def revoke(self, proposal_id: str, *, actor_id: str, now: datetime, reason: str) -> None:
        """Persist a permanent revocation and its audit event atomically."""
        if (not isinstance(actor_id, str) or not actor_id.strip()
                or not isinstance(reason, str) or not reason.strip() or len(reason) > 256
                or not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None):
            raise ValueError("invalid_revocation")
        nested = self._begin_write()
        try:
            proposal = self.get(proposal_id)
            if proposal is None:
                raise ValueError("unknown_proposal")
            self.connection.execute(
                "INSERT INTO approval_revocations(proposal_id,revoked_by,revoked_at_utc,reason) "
                "VALUES (?,?,?,?)",
                (proposal_id, actor_id, now.astimezone(timezone.utc).isoformat(), reason),
            )
            self.connection.execute(
                "INSERT INTO approval_events(proposal_id,actor_id,previous_state,next_state) "
                "VALUES (?,?,?,?)",
                (proposal_id, actor_id, proposal.state, "revoked"),
            )
            self._finish_write(nested, success=True)
        except BaseException:
            self._finish_write(nested, success=False)
            raise

    def is_revoked(self, proposal_id: str) -> bool:
        return self.connection.execute(
            "SELECT 1 FROM approval_revocations WHERE proposal_id=?", (proposal_id,),
        ).fetchone() is not None
