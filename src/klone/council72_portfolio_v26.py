"""Deterministic, budget-limited 9x8 Council72 review portfolio (LAB ONLY).

Produces tentative human-review assignments, never dispatches a model, grants a
capability or changes permissions. Every evidence claim is caller-supplied.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from collections import defaultdict
from collections.abc import Sequence

from .acceptance_matrix import DOMAINS
from .evidence_lineage_v26 import EvidenceLineageNode, analyze_lineage, _id


@dataclass(frozen=True)
class ReviewCandidate:
    task_id: str
    claim_key: str
    domain: str
    ring: int
    seat: int
    priority: int
    estimated_tokens: int
    purpose: str = "review_evidence"

    def __post_init__(self):
        if not _id(self.task_id) or not _id(self.claim_key):
            raise ValueError("invalid_council_task_id")
        if self.domain not in DOMAINS or type(self.domain) is not str:
            raise ValueError("invalid_council_domain")
        if any(type(x) is not int for x in (self.ring, self.seat, self.priority, self.estimated_tokens)):
            raise ValueError("invalid_council_numeric_fields")
        if not (1 <= self.ring <= 9 and 1 <= self.seat <= 8
                and 0 <= self.priority <= 100 and 1 <= self.estimated_tokens <= 100000):
            raise ValueError("invalid_council_task_limits")
        if self.purpose not in ("review_evidence", "request_more_evidence"):
            raise ValueError("invalid_review_purpose")


def plan_council72_review(nodes: Sequence[EvidenceLineageNode],
                          tasks: Sequence[ReviewCandidate], *,
                          max_total_tokens: int = 10000,
                          max_ring_tokens: int = 2500,
                          minimum_candidate_clusters: int = 2) -> dict:
    """Fair round-robin plan across nine rings. No runtime effect or authority."""
    if (not isinstance(tasks, Sequence) or isinstance(tasks, (str, bytes))
            or not 1 <= len(tasks) <= 72):
        raise ValueError("invalid_council_tasks")
    if (type(max_total_tokens) is not int or not 1 <= max_total_tokens <= 1000000
            or type(max_ring_tokens) is not int or not 1 <= max_ring_tokens <= 1000000):
        raise ValueError("invalid_budget")
    lineage = analyze_lineage(nodes, minimum_candidate_clusters=minimum_candidate_clusters)
    claims = {x["claim_key"]: x for x in lineage["claims"]}
    per_ring = defaultdict(list)
    taken_ids, taken_seats = set(), set()
    for item in tasks:
        if not isinstance(item, ReviewCandidate):
            raise ValueError("invalid_council_task")
        if item.task_id in taken_ids or (item.ring, item.seat) in taken_seats:
            raise ValueError("duplicate_task_or_seat")
        taken_ids.add(item.task_id)
        taken_seats.add((item.ring, item.seat))
        if item.claim_key not in claims:
            raise ValueError("unknown_council_claim")
        per_ring[item.ring].append(item)
    for group in per_ring.values():
        group.sort(key=lambda x: (-x.priority, x.task_id))
    remaining = {ring: list(per_ring[ring]) for ring in range(1, 10)}
    allocated_ring = dict.fromkeys(range(1, 10), 0)
    total = 0
    out = []
    # Bounded, deterministic round robin: a ring has at most eight seats.
    for turn in range(8):
        for ring in range(1, 10):
            if turn >= len(remaining[ring]):
                continue
            task = remaining[ring][turn]
            status = claims[task.claim_key]["review_status"]
            if (task.purpose == "review_evidence" and
                    status != "candidate_for_manual_review"):
                reason = "evidence_not_ready_for_review"
            elif task.estimated_tokens > max_ring_tokens - allocated_ring[ring]:
                reason = "ring_token_budget_exceeded"
            elif task.estimated_tokens > max_total_tokens - total:
                reason = "global_token_budget_exceeded"
            else:
                reason = "queued_for_human_review_only"
                total += task.estimated_tokens
                allocated_ring[ring] += task.estimated_tokens
            out.append({
                "task_id": task.task_id, "claim_key": task.claim_key,
                "domain": task.domain, "ring": task.ring, "seat": task.seat,
                "purpose": task.purpose, "estimated_tokens": task.estimated_tokens,
                "review_status": status, "queue_result": reason,
                "execution_enabled": False,
            })
    report = {
        "schema_version": 1, "kind": "klone-council72-portfolio-v26-lab",
        "lineage_analysis_sha256": lineage["analysis_sha256"],
        "tasks": out, "total_task_count": len(tasks),
        "queued_task_count": sum(x["queue_result"] == "queued_for_human_review_only" for x in out),
        "planned_tokens": total,
        "max_total_tokens": max_total_tokens,
        "max_ring_tokens": max_ring_tokens,
        "planned_tokens_per_ring": {str(r): allocated_ring[r] for r in range(1, 10)},
        "planned_tokens_are_estimates": True,
        "resource_usage_enforced": False,
        "source_independence_authenticated": False,
        "actual_hypervisor_authorization_performed": False,
        "human_review_required": True,
        "tasks_executed": False,
        "approval_granted": False,
    }
    payload = json.dumps(report, sort_keys=True, ensure_ascii=True,
                         allow_nan=False, separators=(",", ":")).encode("ascii")
    report["plan_sha256"] = sha256(payload).hexdigest()
    return report
