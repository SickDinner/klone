"""Offline keyring-backed, single-transaction approval gateway.

All components MUST share one SQLite connection with isolation_level=None.
Authentication issuance and real target mutations are deliberately absent.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import sqlite3

from .approval_access import ApprovalAccess
from .approval_identity import SignedActorAssertion
from .approval_keyring import ApprovalKeyring
from .approval_policy import ApprovalProposal
from .approval_session import SessionAssertion


class AtomicApprovalGateway:
    def __init__(self, access: ApprovalAccess, *, keyring: ApprovalKeyring):
        self.access = access
        self.keyring = keyring
        self.connection = access.journal.connection
        if self.connection.isolation_level is not None:
            raise ValueError("autocommit_connection_required")
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS approval_atomic_replay ("
            "assertion_sha256 TEXT PRIMARY KEY)"
        )

    def _run(self, key_id: str, assertion: SignedActorAssertion, now: datetime, action):
        actor = self.keyring.verify(key_id, assertion, now=now)
        return self._run_verified(key_id, assertion.payload, assertion.signature_hex, actor, action)

    def _run_verified(self, key_id: str, payload: bytes, signature_hex: str, actor, action):
        digest = sha256(
            key_id.encode("utf-8") + b"\x00" + payload
            + bytes.fromhex(signature_hex)
        ).hexdigest()
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            self.connection.execute(
                "INSERT INTO approval_atomic_replay(assertion_sha256) VALUES (?)",
                (digest,),
            )
            # The journal methods use BEGIN IMMEDIATE internally. SAVEPOINT
            # keeps their existing rollback behavior while outer transaction
            # controls whether the replay marker is committed.
            result = action(actor)
            self.connection.commit()
            return result
        except sqlite3.IntegrityError as error:
            self.connection.rollback()
            raise PermissionError("actor_assertion_replayed_or_conflict") from error
        except BaseException:
            self.connection.rollback()
            raise

    def propose(
        self, proposal: ApprovalProposal, *, key_id: str,
        assertion: SignedActorAssertion, now: datetime,
    ) -> ApprovalProposal:
        return self._run(key_id, assertion, now, lambda actor:
                         self.access.propose(proposal, actor=actor))

    def transition(
        self, proposal_id: str, next_state: str, *, key_id: str,
        assertion: SignedActorAssertion, now: datetime,
        current_target_version: str | None = None,
        current_patch_sha256: str | None = None,
    ) -> ApprovalProposal:
        return self._run(key_id, assertion, now, lambda actor:
                         self.access.transition(
                             proposal_id, next_state, actor=actor, now=now,
                             current_target_version=current_target_version,
                             current_patch_sha256=current_patch_sha256,
                         ))

    def revoke(
        self, proposal_id: str, *, key_id: str,
        assertion: SignedActorAssertion, now: datetime, reason: str,
    ) -> None:
        return self._run(key_id, assertion, now, lambda actor:
                         self.access.revoke(
                             proposal_id, actor=actor, now=now, reason=reason,
                         ))

    def session_propose(
        self, proposal: ApprovalProposal, *, assertion: SessionAssertion,
        expected_session_id: str, now: datetime,
    ) -> ApprovalProposal:
        actor = self.keyring.verify_session(
            assertion, now=now, expected_session_id=expected_session_id,
        )
        return self._run_verified(
            assertion.key_id, assertion.payload, assertion.signature_hex, actor,
            lambda verified: self.access.propose(proposal, actor=verified),
        )

    def session_transition(
        self, proposal_id: str, next_state: str, *, assertion: SessionAssertion,
        expected_session_id: str, now: datetime,
        current_target_version: str | None = None,
        current_patch_sha256: str | None = None,
    ) -> ApprovalProposal:
        actor = self.keyring.verify_session(
            assertion, now=now, expected_session_id=expected_session_id,
        )
        return self._run_verified(
            assertion.key_id, assertion.payload, assertion.signature_hex, actor,
            lambda verified: self.access.transition(
                proposal_id, next_state, actor=verified, now=now,
                current_target_version=current_target_version,
                current_patch_sha256=current_patch_sha256,
            ),
        )

    def session_revoke(
        self, proposal_id: str, *, assertion: SessionAssertion,
        expected_session_id: str, now: datetime, reason: str,
    ) -> None:
        actor = self.keyring.verify_session(
            assertion, now=now, expected_session_id=expected_session_id,
        )
        return self._run_verified(
            assertion.key_id, assertion.payload, assertion.signature_hex, actor,
            lambda verified: self.access.revoke(
                proposal_id, actor=verified, now=now, reason=reason,
            ),
        )
