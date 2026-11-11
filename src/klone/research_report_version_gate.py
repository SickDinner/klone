"""Fail-closed public research report version and citation gate.

Use a trusted report reader. No raw user-supplied report objects or version
numbers should substitute for authoritative stored history.
"""
from __future__ import annotations

from typing import Callable

from .research_memory import StoredResearchReport
from .research_proposals import ClaimProposal, prepare_claim_proposal


def verify_current_public_report(
    *, proposal: ClaimProposal,
    read_report: Callable[[str, int | None], StoredResearchReport | None],
) -> StoredResearchReport:
    """Require exact, latest public report version and citation membership."""
    if not isinstance(proposal, ClaimProposal) or not callable(read_report):
        raise ValueError("Invalid report verification input")
    expected = prepare_claim_proposal(
        trace_id=proposal.trace_id, report_version=proposal.report_version,
        claim_id=proposal.claim_id, statement=proposal.statement,
        source_refs=proposal.source_refs, requested_status=proposal.requested_status,
        rationale=proposal.rationale)
    if expected != proposal:
        raise ValueError("Proposal integrity mismatch")
    latest = read_report(proposal.trace_id, None)
    if not isinstance(latest, StoredResearchReport):
        raise ValueError("Public report missing")
    if (latest.trace_id != proposal.trace_id
            or latest.version != proposal.report_version
            or latest.room_id != "public-room"):
        raise ValueError("Report version stale or wrong room")
    selected = read_report(proposal.trace_id, proposal.report_version)
    if selected != latest:
        raise ValueError("Report changed between reads")
    if not set(proposal.source_refs).issubset(set(latest.citations)):
        raise ValueError("Proposal cites absent report sources")
    return latest
