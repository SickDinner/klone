"""KLONE privileged research boundary contracts, deliberately non-operational.

This module separates identity, authorization, and write intent. No token
minting, request-header authentication, database write or API endpoint.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json

from .research_proposals import ClaimProposal, prepare_claim_proposal


@dataclass(frozen=True)
class AuthenticatedSession:
    principal: str
    issuer: str
    session_id: str
    verified: bool


@dataclass(frozen=True)
class HypervisorGrant:
    principal: str
    room_id: str
    action: str
    resource_id: str
    version: int
    policy_version: int
    verified: bool


@dataclass(frozen=True)
class ResearchWriteIntent:
    proposal_id: str
    principal: str
    room_id: str
    report_trace_id: str
    report_version: int
    policy_version: int
    fingerprint: str


def prepare_research_write_intent(
    *, proposal: ClaimProposal, session: AuthenticatedSession,
    grant: HypervisorGrant,
) -> ResearchWriteIntent:
    """Reject missing/mismatched trust assertions and bind the exact resource.

    These dataclasses can be forged by callers. This pure function is a
    contract check only, NOT a security boundary or authorization decision.
    """
    if not isinstance(proposal, ClaimProposal):
        raise ValueError("Invalid proposal")
    expected = prepare_claim_proposal(
        trace_id=proposal.trace_id, report_version=proposal.report_version,
        claim_id=proposal.claim_id, statement=proposal.statement,
        source_refs=proposal.source_refs, requested_status=proposal.requested_status,
        rationale=proposal.rationale,
    )
    if proposal != expected:
        raise ValueError("Proposal digest mismatch")
    if not isinstance(session, AuthenticatedSession) or not isinstance(grant, HypervisorGrant):
        raise PermissionError("Session and grant assertions required")
    for value in (session.principal, session.issuer, session.session_id, grant.principal,
                  grant.room_id, grant.action, grant.resource_id):
        if not isinstance(value, str) or not value.strip() or len(value) > 256:
            raise PermissionError("Invalid trust assertion")
    if session.verified is not True or grant.verified is not True:
        raise PermissionError("Unverified trust assertion")
    if session.issuer not in {"local-owner-session", "trusted-service"}:
        raise PermissionError("Unrecognized session issuer")
    if (session.principal != grant.principal or grant.room_id != "public-room"
        or grant.action != "research.claim.commit"
        or grant.resource_id != proposal.trace_id
        or type(grant.version) is not int or grant.version != proposal.report_version
        or type(grant.policy_version) is not int or grant.policy_version < 1):
        raise PermissionError("Grant does not bind exact public report")
    payload = [proposal.proposal_id, session.principal, session.session_id,
               grant.room_id, proposal.trace_id, proposal.report_version,
               grant.policy_version]
    fingerprint = sha256(json.dumps(
        payload, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    return ResearchWriteIntent(
        proposal.proposal_id, session.principal, grant.room_id,
        proposal.trace_id, proposal.report_version, grant.policy_version,
        fingerprint,
    )
