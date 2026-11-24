"""Replayable cross-module review dossier (v2.9 LAB ONLY).

Input metadata, lineage labels, model provider tokens, and routing role claims
are NOT independently attested. The HypervisorRuntime call is a *policy preview*
not an authorization token. No agent execution, storage, network, model call,
approval, signature, or privilege-bearing interface is provided.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
import hmac
import json
import re

from .evidence_lineage_v26 import EvidenceLineageNode, analyze_lineage, _id
from .evidence_counterfactual_v27 import simulate_source_withdrawals
from .council72_portfolio_v26 import ReviewCandidate, plan_council72_review
from .cognition_metabolism_v28 import TaskResourceReceipt, reconcile_council_metabolism

_HASH = re.compile(r"[0-9a-f]{64}\Z")
_MAX_REPORT_BYTES = 131072


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


@dataclass(frozen=True)
class ReviewProofRequest:
    """Bounded planning request. Role/trace are untrusted and confer no authority."""
    task_id: str
    claim_key: str
    room_id: str
    classification_level: str
    actor_role: str
    trace_id: str

    def __post_init__(self) -> None:
        if not all(_id(x) for x in (self.task_id, self.claim_key, self.trace_id)):
            raise ValueError("invalid_review_identity")
        if type(self.room_id) is not str or self.room_id not in {"public-room", "restricted-room", "sealed-room", "sandbox-room", "debug-room"}:
            raise ValueError("invalid_review_room")
        if type(self.classification_level) is not str or self.classification_level not in {"public", "personal", "intimate", "restricted_bio"}:
            raise ValueError("invalid_review_classification")
        if type(self.actor_role) is not str or self.actor_role not in {"owner", "supervisor", "evaluator", "worker", "debugger"}:
            raise ValueError("invalid_review_role")


def _sha(payload: object) -> str:
    return sha256(_canonical(payload)).hexdigest()


def build_review_proof(
    nodes: Sequence[EvidenceLineageNode],
    tasks: Sequence[ReviewCandidate],
    receipts: Sequence[TaskResourceReceipt],
    request: ReviewProofRequest,
    *,
    max_total_tokens: int = 10000,
    max_ring_tokens: int = 2500,
    minimum_candidate_clusters: int = 2,
    max_source_groups: int = 16,
) -> dict:
    """Independently re-evaluate v2.6/v2.7/v2.8 and live *policy preview*.

    All calculations operate on one copied input snapshot. The result is a
    deterministic **unsigned** review dossier, not a credential or proof of
    real-world execution. The source of inputs must be authenticated elsewhere.
    """
    if not isinstance(request, ReviewProofRequest):
        raise ValueError("invalid_review_request")
    if not isinstance(nodes, Sequence) or isinstance(nodes, (str, bytes)):
        raise ValueError("invalid_review_evidence")
    if not isinstance(tasks, Sequence) or isinstance(tasks, (str, bytes)):
        raise ValueError("invalid_review_tasks")
    if not isinstance(receipts, Sequence) or isinstance(receipts, (str, bytes)):
        raise ValueError("invalid_review_receipts")
    fixed_nodes, fixed_tasks, fixed_receipts = tuple(nodes), tuple(tasks), tuple(receipts)
    if len(fixed_nodes) > 512 or len(fixed_tasks) > 72 or len(fixed_receipts) > 72:
        raise ValueError("review_input_too_large")
    # Even metadata such as a claim key can be sensitive. The v2.9 public
    # reviewer is NOT a cross-room reader and never emits private identifiers.
    if (request.room_id != "public-room" or request.classification_level != "public" or
            any(not isinstance(n, EvidenceLineageNode) or
                n.room_id != "public-room" or n.classification != "public"
                for n in fixed_nodes)):
        raise ValueError("nonpublic_evidence_requires_governed_pipeline")

    lineage = analyze_lineage(fixed_nodes, minimum_candidate_clusters=minimum_candidate_clusters)
    withdrawal = simulate_source_withdrawals(
        fixed_nodes, minimum_candidate_clusters=minimum_candidate_clusters,
        max_source_groups=max_source_groups,
    )
    plan = plan_council72_review(
        fixed_nodes, fixed_tasks, max_total_tokens=max_total_tokens,
        max_ring_tokens=max_ring_tokens,
        minimum_candidate_clusters=minimum_candidate_clusters,
    )
    metabolism = reconcile_council_metabolism(plan, fixed_receipts)
    selected = [t for t in plan["tasks"] if t["task_id"] == request.task_id]
    if len(selected) != 1 or selected[0]["claim_key"] != request.claim_key:
        raise ValueError("request_task_claim_mismatch")
    selection = selected[0]
    claim_matches = [x for x in lineage["claims"] if x["claim_key"] == request.claim_key]
    if len(claim_matches) != 1:
        raise ValueError("unknown_request_claim")
    claim = claim_matches[0]
    sensitivity = [x for x in withdrawal["claims"] if x["claim_key"] == request.claim_key]
    if len(sensitivity) != 1:
        raise ValueError("missing_counterfactual_claim")
    sensitivity = sensitivity[0]
    member_nodes = [n for n in fixed_nodes if n.claim_key == request.claim_key]
    if not any(n.domain == selection["domain"] for n in member_nodes):
        raise ValueError("task_claim_domain_mismatch")

    # Recompute the current policy preview: caller-supplied 'allowed' text
    # cannot be substituted for a real HypervisorRuntime decision.
    from .hypervisor_runtime import HypervisorRuntime
    route = HypervisorRuntime().plan(
        room_id=request.room_id, actor_role=request.actor_role,
        permission="propose", trace_id=request.trace_id,
        classification_level=request.classification_level,
    )
    # Route handling is defensive: a future HypervisorRuntime refactor may
    # change/omit fields, but it must never yield approval on uncertainty.
    route_state = route.decision if route.decision in ("allowed", "blocked", "requires_approval") else "unknown"

    holds = []
    if claim["cross_room_or_classification_lineage"]:
        holds.append("claim_scope_or_cross_room_lineage_mismatch")
    if claim["review_status"] != "candidate_for_manual_review":
        holds.append("evidence_not_candidate")
    if selection["queue_result"] != "queued_for_human_review_only":
        holds.append("task_not_queued")
    if route_state != "allowed":
        holds.append("policy_preview_not_allowed")
    if not withdrawal["coverage_complete"]:
        holds.append("counterfactual_coverage_incomplete")
    if sensitivity["single_declared_group_failure_detected"]:
        holds.append("single_group_failure_changes_candidate")
    if (metabolism["review_status"] != "within_reported_budgets_for_review" or
            metabolism["expected_queued_tasks"] == 0 or metabolism["receipt_count"] == 0):
        holds.append("telemetry_needs_review")
    # Even with no holds, source authenticity and the caller's identity are
    # unverified: "packet complete" is never a real-world authorization.
    report = {
        "schema_version": 1,
        "kind": "klone-proof-carrying-cognition-v29-lab",
        "request": {
            "task_id": request.task_id,
            "claim_key": request.claim_key,
            "room_id": request.room_id,
            "classification_level": request.classification_level,
            "actor_role_claim": request.actor_role,
            "trace_id_claim": request.trace_id,
        },
        "parameters": {
            "max_total_tokens": max_total_tokens,
            "max_ring_tokens": max_ring_tokens,
            "minimum_candidate_clusters": minimum_candidate_clusters,
            "max_source_groups": max_source_groups,
        },
        "lineage_analysis_sha256": lineage["analysis_sha256"],
        "evidence_metadata_sha256": lineage["declared_input_sha256"],
        "counterfactual_analysis_sha256": withdrawal["analysis_sha256"],
        "portfolio_plan_sha256": plan["plan_sha256"],
        "metabolism_report_sha256": metabolism["report_sha256"],
        "evidence_review_status": claim["review_status"],
        "source_group_withdrawal_complete": withdrawal["coverage_complete"],
        "source_group_fragility_detected": sensitivity["single_declared_group_failure_detected"],
        "resource_review_status": metabolism["review_status"],
        "resource_receipt_count": metabolism["receipt_count"],
        "resource_expected_tasks": metabolism["expected_queued_tasks"],
        "selected_task_queue_result": selection["queue_result"],
        "hypervisor_policy_preview": {
            "decision": route_state,
            "permission": "propose",
            "room_id": route.room_id,
            "classification": route.classification,
        },
        "review_holds": sorted(holds),
        "review_status": "hold_for_manual_review" if holds else "unverified_packet_ready_for_manual_review",
        "independent_sources_authenticated": False,
        "content_digests_authenticated": False,
        "usage_receipts_authenticated": False,
        "real_world_identity_authenticated": False,
        "hypervisor_execution_authorized": False,
        "external_anchor_verified": False,
        "memory_write_enabled": False,
        "tasks_executed_by_this_module": False,
        "publication_enabled": False,
        "approval_granted": False,
        "human_review_required": True,
    }
    if len(_canonical(report)) > _MAX_REPORT_BYTES - 128:
        raise ValueError("review_report_too_large")
    report["report_sha256"] = _sha({"domain": "klone-v29-report", "report": report})
    return report


def verify_review_proof(
    reported: dict,
    nodes: Sequence[EvidenceLineageNode],
    tasks: Sequence[ReviewCandidate],
    receipts: Sequence[TaskResourceReceipt],
    request: ReviewProofRequest,
    *,
    expected_external_sha256: str | None = None,
    max_total_tokens: int = 10000,
    max_ring_tokens: int = 2500,
    minimum_candidate_clusters: int = 2,
    max_source_groups: int = 16,
) -> dict:
    """Replay comparison; optional caller-pinned hash has no provenance proof.

    Even a true result is *only* proof of local deterministic replay. A
    malicious caller can choose both data and expected digest. No signatures.
    """
    if expected_external_sha256 is not None and (type(expected_external_sha256) is not str or
                                                   not _HASH.fullmatch(expected_external_sha256)):
        raise ValueError("invalid_supplied_external_digest")
    if type(reported) is not dict:
        return {"replay_matches": False, "matches_supplied_digest": False,
                "external_anchor_origin_authenticated": False, "approval_granted": False}
    try:
        if len(_canonical(reported)) > _MAX_REPORT_BYTES:
            raise ValueError("reported_packet_too_large")
        rebuilt = build_review_proof(
            nodes, tasks, receipts, request,
            max_total_tokens=max_total_tokens,
            max_ring_tokens=max_ring_tokens,
            minimum_candidate_clusters=minimum_candidate_clusters,
            max_source_groups=max_source_groups,
        )
        match = hmac.compare_digest(_canonical(reported), _canonical(rebuilt))
        anchored = (expected_external_sha256 is not None and
                    hmac.compare_digest(expected_external_sha256, rebuilt["report_sha256"]))
    except (ValueError, TypeError, OverflowError, RecursionError):
        match = False
        anchored = False
    return {"replay_matches": match,
            "matches_supplied_digest": bool(match and anchored),
            "external_anchor_origin_authenticated": False,
            "approval_granted": False}
