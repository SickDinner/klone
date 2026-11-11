"""Authenticated-context adapter for the offline approval journal.

Authentication MUST happen outside this module. A role label is not proof
of identity. No external endpoints or target mutations are exposed.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .approval_journal import ApprovalJournal
from .approval_policy import ApprovalProposal


@dataclass(frozen=True)
class VerifiedActor:
    actor_id: str
    role: str
    room_id: str
    authenticated: bool


class ApprovalAccess:
    """Deny by default, and never trust an LLM-supplied approval flag."""

    def __init__(self, journal: ApprovalJournal, *, expires_at: dict[str, datetime] | None = None):
        self.journal = journal
        # Optional bootstrap deadlines are persisted when proposals are created.
        self.expires_at = expires_at if expires_at is not None else {}

    @staticmethod
    def _require_actor(actor: VerifiedActor, room_id: str, *, allowed_roles: frozenset[str]) -> None:
        if (not isinstance(actor, VerifiedActor) or not actor.authenticated
                or not isinstance(actor.actor_id, str) or not actor.actor_id.strip()
                or actor.room_id != room_id or actor.role not in allowed_roles):
            raise PermissionError("approval_access_denied")

    def propose(self, proposal: ApprovalProposal, *, actor: VerifiedActor) -> ApprovalProposal:
        self._require_actor(actor, proposal.room_id, allowed_roles=frozenset({"owner", "supervisor"}))
        if actor.actor_id != proposal.proposer_id:
            raise PermissionError("proposer_identity_mismatch")
        return self.journal.propose(\n            proposal, actor_id=actor.actor_id, expires_at=self.expires_at.get(proposal.proposal_id),\n        )

    def transition(
        self, proposal_id: str, next_state: str, *, actor: VerifiedActor,
        now: datetime, current_target_version: str | None = None,
        current_patch_sha256: str | None = None,
    ) -> ApprovalProposal:
        proposal = self.journal.get(proposal_id)
        if proposal is None:
            raise ValueError("unknown_proposal")
        self._require_actor(actor, proposal.room_id, allowed_roles=frozenset({"owner", "supervisor"}))
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("timezone_aware_time_required")
        deadline = self.journal.deadline(proposal_id)
        if next_state in {"approved", "activating", "active"}:
            # Missing expiry is a denial, not unlimited validity.
            if deadline is None or deadline.tzinfo is None or deadline.utcoffset() is None:
                raise PermissionError("approval_expiry_missing")
            if now >= deadline:
                raise PermissionError("approval_expired")
        if next_state == "approved" and actor.role != "owner":
            raise PermissionError("owner_approval_required")
        return self.journal.transition(
            proposal_id, next_state, actor_id=actor.actor_id,
            human_approved=(next_state == "approved" and actor.role == "owner"),
            current_target_version=current_target_version,
            current_patch_sha256=current_patch_sha256,
        )
