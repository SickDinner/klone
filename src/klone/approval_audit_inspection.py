"""Read-only approval audit consistency inspection.

This does not claim cryptographic tamper evidence. It detects missing,
out-of-order, or inconsistent state-transition records.
"""
from __future__ import annotations

from dataclasses import dataclass

from .approval_journal import ApprovalJournal


@dataclass(frozen=True)
class AuditInspection:
    proposal_id: str
    valid: bool
    issues: tuple[str, ...]
    event_count: int


def inspect_approval_audit(journal: ApprovalJournal, proposal_id: str) -> AuditInspection:
    proposal = journal.get(proposal_id)
    if proposal is None:
        return AuditInspection(proposal_id, False, ("unknown_proposal",), 0)
    events = journal.events(proposal_id)
    issues = []
    if not events or events[0].previous_state is not None or events[0].next_state != "proposed":
        issues.append("missing_creation_event")
    previous = None
    for index, event in enumerate(events):
        if index and event.previous_state != previous:
            issues.append("broken_event_chain")
        if not event.actor_id.strip():
            issues.append("missing_actor")
        previous = event.next_state
    expected = "revoked" if journal.is_revoked(proposal_id) else proposal.state
    if previous != expected:
        issues.append("state_event_mismatch")
    return AuditInspection(proposal_id, not issues, tuple(dict.fromkeys(issues)), len(events))
