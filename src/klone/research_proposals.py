from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json


@dataclass(frozen=True)
class ClaimProposal:
    proposal_id: str
    trace_id: str
    report_version: int
    claim_id: str
    statement: str
    source_refs: tuple[str, ...]
    requested_status: str
    rationale: str


def prepare_claim_proposal(
    *, trace_id: str, report_version: int, claim_id: str,
    statement: str, source_refs: tuple[str, ...],
    requested_status: str = "unverified", rationale: str = "",
) -> ClaimProposal:
    """Build a deterministic review-only proposal; never writes to storage.

    This is not authorization or approval. A separate audited privileged
    service must verify identity, permissions and source membership before
    persisting a claim.
    """
    for label, value in (("trace_id", trace_id), ("claim_id", claim_id)):
        if not isinstance(value, str) or not 1 <= len(value) <= 128 or not value.strip():
            raise ValueError(f"Invalid {label}")
    if type(report_version) is not int or report_version < 1:
        raise ValueError("Invalid report version")
    if not isinstance(statement, str) or not statement.strip() or len(statement) > 4000:
        raise ValueError("Invalid claim statement")
    if (not isinstance(source_refs, tuple) or not 1 <= len(source_refs) <= 50
        or any(not isinstance(ref, str) or not ref.strip() or len(ref) > 512
               for ref in source_refs)):
        raise ValueError("Invalid source references")
    if not isinstance(requested_status, str) or requested_status not in {"unverified", "supported", "contested", "retracted"}:
        raise ValueError("Invalid requested status")
    if not isinstance(rationale, str) or len(rationale) > 2000:
        raise ValueError("Invalid rationale")
    if requested_status != "unverified" and not rationale.strip():
        raise ValueError("Reviewed status requires rationale")
    canonical = json.dumps(
        [trace_id, report_version, claim_id, statement, list(source_refs),
         requested_status, rationale], ensure_ascii=False, separators=(",", ":"),
    )
    proposal_id = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return ClaimProposal(proposal_id, trace_id, report_version, claim_id,
                         statement, source_refs, requested_status, rationale)


def verify_claim_proposal(proposal: ClaimProposal, *, memory) -> bool:
    """Validate immutable proposal identity and public report provenance.

    No authorization, approval, or mutation occurs. A privileged caller must
    authenticate the reviewer and audit its decision separately.
    """
    if not isinstance(proposal, ClaimProposal):
        raise ValueError("Expected claim proposal")
    expected = prepare_claim_proposal(
        trace_id=proposal.trace_id, report_version=proposal.report_version,
        claim_id=proposal.claim_id, statement=proposal.statement,
        source_refs=proposal.source_refs, requested_status=proposal.requested_status,
        rationale=proposal.rationale,
    )
    if proposal.proposal_id != expected.proposal_id:
        raise ValueError("Proposal content digest mismatch")
    report = memory.read(trace_id=proposal.trace_id, version=proposal.report_version)
    if report is None or report.room_id != "public-room":
        raise ValueError("Verified public report not found")
    if any(ref not in report.citations for ref in proposal.source_refs):
        raise ValueError("Proposal references absent from report")
    return True
