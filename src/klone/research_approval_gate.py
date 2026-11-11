"""Fail-closed approval preflight for KLONE research claims.

No persistence or authority is granted here. In particular, request headers
and RequestContext are NOT authenticated identities. This preflight is a
pure policy check for a future trusted, transactional approval boundary.
"""
from __future__ import annotations

from dataclasses import dataclass

from .research_proposals import ClaimProposal, verify_claim_proposal
from .research_review_bundle import ReviewBundle, prepare_review_bundle
from .genomics_hypotheses import Hypothesis, EvidenceItem


@dataclass(frozen=True)
class TrustedReviewer:
    """An identity assertion issued only by an external trusted authenticator.

    Constructing this dataclass is not authentication. Callers MUST NOT derive
    it from user-supplied headers, roles, or arbitrary API request payloads.
    """
    principal: str
    authenticator: str
    authenticated: bool
    authorized_for_public_evidence: bool


@dataclass(frozen=True)
class ApprovalPreflight:
    allowed: bool
    reason: str
    proposal_id: str


def check_approval_preflight(
    *, proposal: ClaimProposal, bundle: ReviewBundle,
    reviewer: TrustedReviewer, memory,
    hypotheses: tuple[Hypothesis, ...], evidence: tuple[EvidenceItem, ...],
) -> ApprovalPreflight:
    """Validate integrity and deny unless all external authority gates are met.

    Even an allowed result is NOT permission to call EvidenceLedger.append:
    privileged service must atomically audit and persist in one transaction.
    """
    if not isinstance(proposal, ClaimProposal) or not isinstance(bundle, ReviewBundle):
        raise ValueError("Invalid proposal or bundle")
    if not isinstance(reviewer, TrustedReviewer):
        raise ValueError("Trusted reviewer assertion required")
    if (not isinstance(reviewer.principal, str) or not reviewer.principal.strip()
        or len(reviewer.principal) > 128
        or not isinstance(reviewer.authenticator, str)
        or reviewer.authenticator not in {"local-owner-session", "trusted-service"}):
        return ApprovalPreflight(False, "invalid_reviewer_assertion", proposal.proposal_id)
    if reviewer.authenticated is not True:
        return ApprovalPreflight(False, "identity_not_authenticated", proposal.proposal_id)
    if reviewer.authorized_for_public_evidence is not True:
        return ApprovalPreflight(False, "public_evidence_permission_denied", proposal.proposal_id)
    verify_claim_proposal(proposal, memory=memory)
    expected_bundle = prepare_review_bundle(
        proposal=proposal, hypotheses=hypotheses, evidence=evidence)
    if (bundle != expected_bundle
        or bundle.proposal_id != proposal.proposal_id
        or bundle.report_trace_id != proposal.trace_id
        or bundle.report_version != proposal.report_version
        or bundle.disposition != "human_review_required"
        or not isinstance(bundle.bundle_id, str) or len(bundle.bundle_id) != 64):
        return ApprovalPreflight(False, "review_bundle_mismatch", proposal.proposal_id)
    return ApprovalPreflight(True, "preflight_only_no_write_authority", proposal.proposal_id)
