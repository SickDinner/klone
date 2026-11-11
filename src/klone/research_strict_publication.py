"""Strict co-located SQLite publication entrypoint.

Requires caller-provided authenticated identity and current policy authority.
The policy guard MUST consult authoritative policy under the same SQLite
transaction (or an externally serialized, fail-closed authority).
"""
from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Callable

from .genomics_hypotheses import EvidenceItem, Hypothesis
from .hypervisor_runtime import HypervisorRuntime
from .research_atomic_ledger import CommitReceipt
from .research_proposals import ClaimProposal
from .research_review_bundle import ReviewBundle
from .research_signed_grants import SignedResearchGrant
from .research_source_manifest import PublicSourceManifest
from .research_trusted_publication import publish_trusted_research_claim
from .research_transaction_report_gate import require_current_report_in_transaction


def publish_strict_public_claim(
    *, database_path: Path, proposal: ClaimProposal, bundle: ReviewBundle,
    hypotheses: tuple[Hypothesis, ...], evidence: tuple[EvidenceItem, ...],
    manifests: dict[str, PublicSourceManifest], source_bytes: dict[str, bytes],
    grant: SignedResearchGrant, principal: str, actor_role: str,
    policy_version: int, now: int, key: bytes, decision_reason: str,
    authenticate: Callable[[str, str], bool],
    authorize_commit: Callable[[str, str, str], bool],
    transaction_policy: Callable[[sqlite3.Connection, str, str, int], None],
    runtime: HypervisorRuntime,
) -> CommitReceipt:
    """Enforce report freshness and policy together before any claim write."""
    if not callable(transaction_policy):
        raise PermissionError("Transaction-scoped policy authority required")

    def guard(db: sqlite3.Connection, who: str, claim: str, version: int) -> None:
        require_current_report_in_transaction(db, proposal)
        transaction_policy(db, who, claim, version)

    return publish_trusted_research_claim(
        database_path=database_path, proposal=proposal, bundle=bundle,
        hypotheses=hypotheses, evidence=evidence,
        manifests=manifests, source_bytes=source_bytes, grant=grant,
        principal=principal, actor_role=actor_role, policy_version=policy_version,
        now=now, key=key, decision_reason=decision_reason,
        authenticate=authenticate, authorize_commit=authorize_commit,
        commit_policy_guard=guard, runtime=runtime)
