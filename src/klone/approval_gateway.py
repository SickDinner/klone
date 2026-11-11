"""Offline composition of signed actor verification and approval access.

Caller must obtain a signed assertion from a trusted authentication issuer.
No token issuer, HTTP endpoint, or mutation is provided here.
"""
from __future__ import annotations

from datetime import datetime

from .approval_access import ApprovalAccess
from .approval_identity import SignedActorAssertion
from .approval_replay import AssertionReplayGuard
from .approval_policy import ApprovalProposal


class ApprovalGateway:
    def __init__(self, access: ApprovalAccess, replay: AssertionReplayGuard, *, secret: bytes):
        if not isinstance(secret, bytes) or len(secret) < 32:
            raise ValueError("server_signing_secret_required")
        self.access = access
        self.replay = replay
        self.secret = secret

    def propose(
        self, proposal: ApprovalProposal, *, assertion: SignedActorAssertion, now: datetime,
    ) -> ApprovalProposal:
        actor = self.replay.verify_once(assertion, secret=self.secret, now=now)
        return self.access.propose(proposal, actor=actor)

    def transition(
        self, proposal_id: str, next_state: str, *, assertion: SignedActorAssertion,
        now: datetime, current_target_version: str | None = None,
        current_patch_sha256: str | None = None,
    ) -> ApprovalProposal:
        actor = self.replay.verify_once(assertion, secret=self.secret, now=now)
        return self.access.transition(
            proposal_id, next_state, actor=actor, now=now,
            current_target_version=current_target_version,
            current_patch_sha256=current_patch_sha256,
        )

    def revoke(
        self, proposal_id: str, *, assertion: SignedActorAssertion, now: datetime, reason: str,
    ) -> None:
        actor = self.replay.verify_once(assertion, secret=self.secret, now=now)
        self.access.revoke(proposal_id, actor=actor, now=now, reason=reason)
