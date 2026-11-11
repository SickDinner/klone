"""Fail-closed preflight for a trusted KLONE research publication service.

This module checks the immutable review handoff and source membership.
The caller must separately authenticate the reviewer and obtain a fresh
Hypervisor decision before invoking the atomic signed-grant commit.
"""
from __future__ import annotations

from dataclasses import dataclass

from .genomics_hypotheses import EvidenceItem, Hypothesis
from .research_proposals import ClaimProposal
from .research_review_bundle import ReviewBundle, prepare_review_bundle
from .research_dossier import ResearchDossier, build_dossier
from .research_source_manifest import PublicSourceManifest, verify_public_source


@dataclass(frozen=True)
class PublicationPreflight:
    proposal_id: str
    bundle_id: str
    verified_source_ids: tuple[str, ...]


def preflight_publication(
    *, proposal: ClaimProposal, bundle: ReviewBundle,
    hypotheses: tuple[Hypothesis, ...], evidence: tuple[EvidenceItem, ...],
    manifests: dict[str, PublicSourceManifest],
    source_bytes: dict[str, bytes],
) -> PublicationPreflight:
    """Verify review handoff and source bytes without writing any state."""
    expected = prepare_review_bundle(
        proposal=proposal, hypotheses=hypotheses, evidence=evidence)
    if bundle != expected:
        raise ValueError("Review bundle integrity mismatch")
    if not isinstance(manifests, dict) or not isinstance(source_bytes, dict):
        raise ValueError("Invalid source dictionaries")
    if len(manifests) > 5000 or len(source_bytes) > 5000:
        raise ValueError("Too many sources")
    evidence_refs = {item.source_ref for item in evidence}
    if not set(proposal.source_refs).issubset(evidence_refs):
        raise ValueError("Proposal references not present in evidence")
    verified = []
    for ref in sorted(evidence_refs):
        manifest, content = manifests.get(ref), source_bytes.get(ref)
        if (not isinstance(manifest, PublicSourceManifest)
                or manifest.source_id != ref
                or type(content) is not bytes
                or not verify_public_source(manifest, content)):
            raise ValueError("Source integrity check failed")
        verified.append(ref)
    return PublicationPreflight(proposal.proposal_id, bundle.bundle_id,
                                tuple(verified))
