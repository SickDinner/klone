"""Offline approval audit digest, for externally anchored checkpoints.

A digest alone does not prevent a database administrator from rewriting history.
Persist and sign checkpoints in a separately trusted system before relying on
them for tamper evidence.
"""
from __future__ import annotations

from hashlib import sha256
import json

from .approval_audit_inspection import inspect_approval_audit
from .approval_journal import ApprovalJournal


def approval_audit_digest(journal: ApprovalJournal, proposal_id: str) -> str:
    inspection = inspect_approval_audit(journal, proposal_id)
    if not inspection.valid:
        raise ValueError("approval_audit_inconsistent")
    proposal = journal.get(proposal_id)
    events = journal.events(proposal_id)
    document = {
        "domain": "klone-approval-audit-v1",
        "proposal": {
            "id": proposal.proposal_id,
            "proposer": proposal.proposer_id,
            "room": proposal.room_id,
            "version": proposal.target_version,
            "patch_sha256": proposal.patch_sha256,
            "state": proposal.state,
            "approver": proposal.approver_id,
            "revoked": journal.is_revoked(proposal_id),
        },
        "deadline": (
            journal.deadline(proposal_id).isoformat()
            if journal.deadline(proposal_id) is not None else None
        ),
        "events": [
            [event.proposal_id, event.actor_id, event.previous_state, event.next_state]
            for event in events
        ],
    }
    encoded = json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()
