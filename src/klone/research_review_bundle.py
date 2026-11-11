"""Deterministic, read-only KLONE research review bundle.

Collects independent research components into an auditable handoff manifest.
No authorization, persistence, inference, remote agent execution or approval.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json

from .genomics_hypotheses import EvidenceItem, Hypothesis, evaluate_hypotheses
from .research_proposals import ClaimProposal, prepare_claim_proposal


@dataclass(frozen=True)
class ReviewBundle:
    bundle_id: str
    proposal_id: str
    hypothesis_fingerprint: str
    report_trace_id: str
    report_version: int
    risk_flags: tuple[str, ...]
    disposition: str


def prepare_review_bundle(
    *, proposal: ClaimProposal,
    hypotheses: tuple[Hypothesis, ...],
    evidence: tuple[EvidenceItem, ...],
) -> ReviewBundle:
    """Prepare a reproducible handoff, never grant claim write permission."""
    if not isinstance(proposal, ClaimProposal):
        raise ValueError("Invalid proposal")
    expected = prepare_claim_proposal(
        trace_id=proposal.trace_id, report_version=proposal.report_version,
        claim_id=proposal.claim_id, statement=proposal.statement,
        source_refs=proposal.source_refs, requested_status=proposal.requested_status,
        rationale=proposal.rationale,
    )
    if expected != proposal:
        raise ValueError("Tampered proposal")
    result = evaluate_hypotheses(hypotheses, evidence)
    flags = set()
    if not hypotheses:
        flags.add("no_hypotheses")
    if not evidence:
        flags.add("no_evidence")
    if any(row["contradiction_groups"] for row in result["results"]):
        flags.add("contradictory_evidence")
    if any(row["uncertain_groups"] for row in result["results"]):
        flags.add("uncertain_evidence")
    if any(row["support_groups"] == 0 for row in result["results"]):
        flags.add("missing_support")
    if proposal.requested_status != "unverified":
        flags.add("reviewed_status_requires_privileged_approval")
    canonical = json.dumps(
        [proposal.proposal_id, result["fingerprint"], sorted(flags)],
        ensure_ascii=False, separators=(",", ":"),
    )
    return ReviewBundle(
        sha256(canonical.encode("utf-8")).hexdigest(),
        proposal.proposal_id, result["fingerprint"],
        proposal.trace_id, proposal.report_version,
        tuple(sorted(flags)), "human_review_required",
    )
