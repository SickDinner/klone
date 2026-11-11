"""Trusted-service publication orchestration with explicit policy checks.

The caller MUST authenticate principal, secure its signing key and database,
and supply the current policy version from its authoritative policy store.
Preflight is read-only and occurs before the atomic claim/audit/nonce commit.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable
import sqlite3

from .genomics_hypotheses import Hypothesis, EvidenceItem
from .hypervisor_runtime import HypervisorRuntime
from .research_atomic_grant_commit import commit_claim_with_grant
from .research_atomic_ledger import CommitReceipt
from .research_proposals import ClaimProposal
from .research_review_bundle import ReviewBundle
from .research_source_manifest import PublicSourceManifest
from .research_signed_grants import SignedResearchGrant
from .research_publication_preflight import preflight_publication


def publish_trusted_research_claim(
    *, database_path: Path, proposal: ClaimProposal, bundle: ReviewBundle,
    hypotheses: tuple[Hypothesis, ...], evidence: tuple[EvidenceItem, ...],
    manifests: dict[str, PublicSourceManifest], source_bytes: dict[str, bytes],
    grant: SignedResearchGrant, principal: str, actor_role: str,
    policy_version: int, now: int, key: bytes, decision_reason: str,
    authenticate: Callable[[str, str], bool],
    authorize_commit: Callable[[str, str, str], bool],
    runtime: HypervisorRuntime,
    commit_policy_guard: Callable[[sqlite3.Connection, str, str, int], None] | None = None,
) -> CommitReceipt:
    """No state changes until authentication, policy and evidence checks pass.

    Policy and identity must be supplied by trusted infrastructure, never
    copied directly from request parameters. Current policy is rechecked by
    the caller if it may change concurrently with the SQLite transaction.
    """
    if (not callable(authenticate) or not callable(authorize_commit)
            or not isinstance(runtime, HypervisorRuntime)):
        raise PermissionError("Trusted authentication and policy required")
    if not authenticate(principal, actor_role):
        raise PermissionError("Principal authentication failed")
    route = runtime.plan(
        room_id="public-room", actor_role=actor_role, permission="propose",
        trace_id=proposal.trace_id, classification_level="public")
    if route.decision != "allowed":
        raise PermissionError("Hypervisor denied research proposal")
    # Public-room permits proposals, not writes. A separately privileged
    # service must authorize the commit under current policy.
    if not authorize_commit(principal, proposal.claim_id, actor_role):
        raise PermissionError("Privileged commit authorization denied")
    if commit_policy_guard is not None and not callable(commit_policy_guard):
        raise PermissionError("Invalid transaction policy guard")
    preflight_publication(
        proposal=proposal, bundle=bundle, hypotheses=hypotheses,
        evidence=evidence, manifests=manifests, source_bytes=source_bytes)
    return commit_claim_with_grant(
        database_path=database_path, proposal=proposal, grant=grant,
        principal=principal, policy_version=policy_version, now=now,
        key=key, decision_reason=decision_reason,
        transaction_guard=(
            None if commit_policy_guard is None else
            lambda connection: commit_policy_guard(
                connection, principal, proposal.claim_id, policy_version)))
