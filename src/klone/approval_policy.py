"""Pure approval state-machine prototype; does not activate mutations."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

State = Literal["proposed", "validated", "awaiting_approval", "approved", "activating", "active", "rejected", "expired", "failed", "rolled_back"]

TRANSITIONS: dict[str, frozenset[str]] = {
    "proposed": frozenset(("validated", "rejected")),
    "validated": frozenset(("awaiting_approval", "rejected")),
    "awaiting_approval": frozenset(("approved", "rejected", "expired")),
    "approved": frozenset(("activating", "expired")),
    "activating": frozenset(("active", "failed")),
    "active": frozenset(("rolled_back",)),
    "rejected": frozenset(),
    "expired": frozenset(),
    "failed": frozenset(),
    "rolled_back": frozenset(),
}


@dataclass(frozen=True)
class ApprovalProposal:
    proposal_id: str
    proposer_id: str
    room_id: str
    target_version: str
    patch_sha256: str
    state: State = "proposed"
    approver_id: str | None = None


def advance_proposal(
    proposal: ApprovalProposal,
    next_state: State,
    *,
    actor_id: str,
    human_approved: bool = False,
    current_target_version: str | None = None,
    current_patch_sha256: str | None = None,
) -> ApprovalProposal:
    """Validate transitions only. Persistence, authentication and audit are external."""
    if not actor_id or next_state not in TRANSITIONS.get(proposal.state, frozenset()):
        raise ValueError("invalid_transition")
    if next_state == "approved":
        if not human_approved or actor_id == proposal.proposer_id:
            raise PermissionError("independent_human_approval_required")
        if current_target_version != proposal.target_version:
            raise ValueError("stale_target_version")
        if current_patch_sha256 != proposal.patch_sha256:
            raise ValueError("patch_changed")
        return replace(proposal, state=next_state, approver_id=actor_id)
    if next_state == "activating":
        if not proposal.approver_id or current_target_version != proposal.target_version:
            raise ValueError("activation_precondition_failed")
        if current_patch_sha256 != proposal.patch_sha256:
            raise ValueError("patch_changed")
    return replace(proposal, state=next_state)
