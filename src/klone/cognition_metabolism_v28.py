"""Process-scoped telemetry and Council72 budget reconciliation (v2.8 LAB).

No model invocation, remote metrics, automated enforcement, approvals, or writes.
Process CPU/RSS are not attributable to individual concurrent agents; provider
reported tokens are not measured by the OS or verified by this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
import re
import time
from collections.abc import Sequence

from .evidence_lineage_v26 import _id

_HEX = re.compile(r"[0-9a-f]{64}\Z")
_MAX_NS = 2**63 - 1
_MAX_BYTES = 2**50
_MAX_TOKENS = 10_000_000


def _integer(value: object, maximum: int = _MAX_NS) -> bool:
    return type(value) is int and 0 <= value <= maximum


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=True,
                      separators=(",", ":"), allow_nan=False).encode("ascii")


def _self_rss_bytes() -> int | None:
    """Linux/Termux current process VmRSS; not peak RSS, no foreign process."""
    try:
        with open("/proc/self/status", encoding="ascii") as handle:
            content = handle.read(65536)
        match = re.search(r"^VmRSS:\s*([0-9]+)\s+kB\s*$", content, re.MULTILINE)
        if match is not None:
            rss = int(match.group(1)) * 1024
            return rss if _integer(rss, _MAX_BYTES) else None
    except (OSError, UnicodeError, ValueError, OverflowError):
        pass
    return None


@dataclass(frozen=True)
class ProcessSnapshot:
    pid: int
    monotonic_ns: int
    process_cpu_ns: int
    current_rss_bytes: int | None

    def __post_init__(self) -> None:
        if type(self.pid) is not int or self.pid <= 0:
            raise ValueError("invalid_process_id")
        if not _integer(self.monotonic_ns) or not _integer(self.process_cpu_ns):
            raise ValueError("invalid_process_clock")
        if self.current_rss_bytes is not None and not _integer(self.current_rss_bytes, _MAX_BYTES):
            raise ValueError("invalid_process_rss")


def capture_process_snapshot() -> ProcessSnapshot:
    """Capture current-process clocks; RSS unknown when OS does not expose it."""
    return ProcessSnapshot(pid=os.getpid(), monotonic_ns=time.monotonic_ns(),
                           process_cpu_ns=time.process_time_ns(),
                           current_rss_bytes=_self_rss_bytes())


@dataclass(frozen=True)
class ProviderTokenUsage:
    """Unverified external-provider report. None signifies missing usage."""
    prompt_tokens: int | None
    completion_tokens: int | None

    def __post_init__(self) -> None:
        both = self.prompt_tokens is None and self.completion_tokens is None
        complete = _integer(self.prompt_tokens, _MAX_TOKENS) and _integer(self.completion_tokens, _MAX_TOKENS)
        if not (both or complete):
            raise ValueError("incomplete_or_invalid_token_report")
        if complete and self.prompt_tokens + self.completion_tokens > _MAX_TOKENS:
            raise ValueError("token_report_too_large")

    @property
    def total(self) -> int | None:
        return None if self.prompt_tokens is None else self.prompt_tokens + self.completion_tokens


@dataclass(frozen=True)
class TaskResourceReceipt:
    task_id: str
    ring: int
    seat: int
    plan_sha256: str
    start: ProcessSnapshot
    end: ProcessSnapshot
    provider_usage: ProviderTokenUsage
    outcome: str  # completed, failed, cancelled, never implies authority

    def __post_init__(self) -> None:
        if not _id(self.task_id) or type(self.ring) is not int or not 1 <= self.ring <= 9:
            raise ValueError("invalid_receipt_task")
        if type(self.seat) is not int or not 1 <= self.seat <= 8:
            raise ValueError("invalid_receipt_seat")
        if type(self.plan_sha256) is not str or not _HEX.fullmatch(self.plan_sha256):
            raise ValueError("invalid_receipt_plan")
        if not isinstance(self.start, ProcessSnapshot) or not isinstance(self.end, ProcessSnapshot):
            raise ValueError("invalid_receipt_snapshots")
        if self.start.pid != self.end.pid:
            raise ValueError("different_process_snapshots")
        if (self.end.monotonic_ns < self.start.monotonic_ns or
                self.end.process_cpu_ns < self.start.process_cpu_ns):
            raise ValueError("non_monotonic_receipt")
        if not isinstance(self.provider_usage, ProviderTokenUsage):
            raise ValueError("invalid_token_usage")
        if type(self.outcome) is not str or self.outcome not in {"completed", "failed", "cancelled"}:
            raise ValueError("invalid_receipt_outcome")


def _validated_plan(plan: dict) -> dict[str, dict]:
    """Validate a v2.6 planning artifact; its hash is only an integrity check."""
    if (type(plan) is not dict or type(plan.get("schema_version")) is not int or
            plan["schema_version"] != 1 or type(plan.get("kind")) is not str or
            plan["kind"] != "klone-council72-portfolio-v26-lab"):
        raise ValueError("invalid_portfolio_artifact")
    digest = plan.get("plan_sha256")
    if type(digest) is not str or not _HEX.fullmatch(digest):
        raise ValueError("missing_portfolio_hash")
    try:
        if sha256(_json_bytes({k: v for k, v in plan.items() if k != "plan_sha256"})).hexdigest() != digest:
            raise ValueError("modified_portfolio_artifact")
    except (TypeError, OverflowError, ValueError) as exc:
        raise ValueError("invalid_portfolio_integrity") from exc
    tasks = plan.get("tasks")
    if not isinstance(tasks, list) or not 1 <= len(tasks) <= 72:
        raise ValueError("invalid_portfolio_tasks")
    if not (_integer(plan.get("max_total_tokens"), 1_000_000) and
            _integer(plan.get("max_ring_tokens"), 1_000_000) and
            plan["max_total_tokens"] > 0 and plan["max_ring_tokens"] > 0):
        raise ValueError("invalid_portfolio_budgets")
    if plan.get("tasks_executed") is not False or plan.get("approval_granted") is not False:
        raise ValueError("plan_is_not_review_only")
    found = {}
    seen_seats = set()
    planned = 0
    ring_sums = dict.fromkeys(range(1, 10), 0)
    for task in tasks:
        if type(task) is not dict:
            raise ValueError("invalid_portfolio_task")
        ident, ring, seat, estimate = (task.get(k) for k in ("task_id", "ring", "seat", "estimated_tokens"))
        if not _id(ident) or not (type(ring) is int and 1 <= ring <= 9 and
                type(seat) is int and 1 <= seat <= 8 and _integer(estimate, 100000) and estimate > 0):
            raise ValueError("invalid_portfolio_task_fields")
        if ident in found or (ring, seat) in seen_seats:
            raise ValueError("duplicate_portfolio_task_or_seat")
        if type(task.get("queue_result")) is not str or task["queue_result"] not in {"queued_for_human_review_only", "evidence_not_ready_for_review",
                                            "ring_token_budget_exceeded", "global_token_budget_exceeded"}:
            raise ValueError("invalid_portfolio_decision")
        seen_seats.add((ring, seat))
        found[ident] = task
        if task["queue_result"] == "queued_for_human_review_only":
            planned += estimate
            ring_sums[ring] += estimate
    if (planned != plan.get("planned_tokens") or
            planned > plan["max_total_tokens"] or
            any(v > plan["max_ring_tokens"] for v in ring_sums.values()) or
            sum(t["queue_result"] == "queued_for_human_review_only" for t in tasks) != plan.get("queued_task_count") or
            plan.get("total_task_count") != len(tasks) or
            plan.get("planned_tokens_per_ring") != {str(r): ring_sums[r] for r in range(1, 10)}):
        raise ValueError("inconsistent_portfolio_budget")
    return found


def reconcile_council_metabolism(plan: dict, receipts: Sequence[TaskResourceReceipt]) -> dict:
    """Evaluate reported resource claims, not grant budget or approve execution.

    Missing usage, missing receipt, cancelled/failed work, overlap, and
    overruns remain visible. No external effects and no task dispatch.
    """
    tasks = _validated_plan(plan)
    if (not isinstance(receipts, Sequence) or isinstance(receipts, (str, bytes))
            or len(receipts) > 72):
        raise ValueError("invalid_resource_receipts")
    seen: dict[str, TaskResourceReceipt] = {}
    intervals: dict[int, list[tuple[int, int]]] = {}
    for receipt in receipts:
        if not isinstance(receipt, TaskResourceReceipt):
            raise ValueError("invalid_resource_receipt")
        if receipt.task_id in seen:
            raise ValueError("duplicate_resource_receipt")
        task = tasks.get(receipt.task_id)
        if task is None or task["queue_result"] != "queued_for_human_review_only":
            raise ValueError("receipt_for_unqueued_task")
        if ((task["ring"], task["seat"]) != (receipt.ring, receipt.seat) or
                receipt.plan_sha256 != plan["plan_sha256"]):
            raise ValueError("receipt_plan_scope_mismatch")
        seen[receipt.task_id] = receipt
        intervals.setdefault(receipt.start.pid, []).append(
            (receipt.start.monotonic_ns, receipt.end.monotonic_ns))
    overlap = any(left[1] > right[0]
                  for spans in intervals.values()
                  for left, right in zip(sorted(spans), sorted(spans)[1:]))
    expected = {tid for tid, task in tasks.items() if task["queue_result"] == "queued_for_human_review_only"}
    missing_ids = sorted(expected.difference(seen))
    tokens_by_ring = dict.fromkeys(range(1, 10), 0)
    token_total = 0
    missing_usage = []
    failed_tasks = []
    estimate_exceeded = []
    cpu_total = 0
    wall_total = 0
    rss_available = 0
    rows = []
    for task_id in sorted(seen):
        r = seen[task_id]
        tok = r.provider_usage.total
        if tok is None:
            missing_usage.append(task_id)
        else:
            token_total += tok
            tokens_by_ring[r.ring] += tok
            if tok > tasks[task_id]["estimated_tokens"]:
                estimate_exceeded.append(task_id)
        if r.outcome != "completed":
            failed_tasks.append(task_id)
        wall = r.end.monotonic_ns - r.start.monotonic_ns
        cpu = r.end.process_cpu_ns - r.start.process_cpu_ns
        wall_total += wall
        cpu_total += cpu
        rss_available += r.end.current_rss_bytes is not None
        rows.append({"task_id": task_id, "ring": r.ring, "seat": r.seat,
                     "outcome": r.outcome, "process_wall_ns": wall,
                     "process_cpu_ns": cpu,
                     "process_current_rss_bytes_after": r.end.current_rss_bytes,
                     "provider_reported_tokens": tok,
                     "planned_estimated_tokens": tasks[task_id]["estimated_tokens"]})
    exceed = token_total > plan["max_total_tokens"] or any(
        tokens_by_ring[r] > plan["max_ring_tokens"] for r in range(1, 10))
    if exceed:
        state = "reported_budget_exceeded"
    elif missing_ids or missing_usage:
        state = "insufficient_telemetry"
    elif failed_tasks:
        state = "incomplete_or_failed_work"
    elif overlap:
        state = "process_intervals_overlap"
    elif estimate_exceeded:
        state = "task_estimate_exceeded"
    else:
        state = "within_reported_budgets_for_review"
    report = {
        "schema_version": 1, "kind": "klone-cognition-metabolism-v28-lab",
        "plan_sha256": plan["plan_sha256"],
        "review_status": state,
        "expected_queued_tasks": len(expected),
        "receipt_count": len(seen),
        "missing_task_ids": missing_ids,
        "missing_provider_usage_task_ids": missing_usage,
        "incomplete_task_ids": failed_tasks,
        "estimate_exceeded_task_ids": estimate_exceeded,
        "reported_token_total_known_only": token_total,
        "reported_tokens_per_ring_known_only": {str(r): tokens_by_ring[r] for r in range(1, 10)},
        "cpu_total_ns_if_nonoverlapping": None if overlap else cpu_total,
        "process_wall_ns_sum_nonunique": wall_total,
        "rss_samples_available": rss_available,
        "process_intervals_overlap": overlap,
        "rows": rows,
        "token_source": "caller_supplied_provider_report_unverified",
        "cpu_source": "process_wide_cpu_not_per_agent",
        "rss_source": "process_current_rss_optional_not_peak_or_isolated",
        "energy_joules": None,
        "device_thermal_state": None,
        "telemetry_authenticated": False,
        "resource_limit_enforced": False,
        "human_review_required": True,
        "execution_enabled": False,
        "approval_granted": False,
    }
    report["report_sha256"] = sha256(_json_bytes(report)).hexdigest()
    return report
