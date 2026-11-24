"""KLONE v3.1 LAB: deterministic Mission Control review evidence, never authority.

Combines the actual v3.0 public-memory continuity check, the 12-domain
acceptance matrix, a commit-pinned but *unattested* test-result matrix, and an
optional rebuilt v2.9 proof dossier. Does no I/O, network, file operations,
model calls, authentication, task dispatch, storage or capability issuance.

No private-room data is accepted; no source identifiers or memory contents are
included in output. Caller-supplied run labels/commits are NOT authenticated.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
import hmac
import json
import re

from .acceptance_matrix import DOMAINS
from .memory_continuity_v30 import PublicMemoryEvent
from .system_readiness_v30 import build_system_review_pulse

_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_SHA64 = re.compile(r"[0-9a-f]{64}\Z")
_MISSING = ("android:3.13", "ubuntu:3.11", "ubuntu:3.12",
            "windows:3.11", "windows:3.12")
_MAX_REPORT_BYTES = 65536
_MAX_RUNS = 8


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


@dataclass(frozen=True)
class RegressionRunClaim:
    """A claim about tests, not a CI attestation or a device identity proof."""
    environment: str
    python_version: str
    commit_sha: str
    test_count: int
    skipped: int
    result: str
    source_kind: str
    record_sha256: str | None = None

    def __post_init__(self) -> None:
        if type(self.environment) is not str or self.environment not in ("android", "ubuntu", "windows"):
            raise ValueError("invalid_regression_environment")
        if type(self.python_version) is not str or self.python_version not in ("3.11", "3.12", "3.13"):
            raise ValueError("invalid_regression_python")
        if self.environment == "android" and self.python_version != "3.13":
            raise ValueError("unsupported_android_matrix_key")
        if self.environment in ("ubuntu", "windows") and self.python_version == "3.13":
            raise ValueError("unsupported_ci_matrix_key")
        if type(self.commit_sha) is not str or not _SHA40.fullmatch(self.commit_sha):
            raise ValueError("invalid_regression_commit")
        if (type(self.test_count) is not int or not 1 <= self.test_count <= 100000 or
                type(self.skipped) is not int or not 0 <= self.skipped < self.test_count):
            raise ValueError("invalid_regression_counts")
        if type(self.result) is not str or self.result not in ("passed", "failed"):
            raise ValueError("invalid_regression_result")
        if type(self.source_kind) is not str or self.source_kind not in (
                "operator_log_claim", "github_actions_claim"):
            raise ValueError("invalid_regression_source_kind")
        if self.environment == "android" and self.source_kind != "operator_log_claim":
            raise ValueError("android_origin_claim_mismatch")
        if self.environment != "android" and self.source_kind != "github_actions_claim":
            raise ValueError("ci_origin_claim_mismatch")
        if self.record_sha256 is not None and (
                type(self.record_sha256) is not str or not _SHA64.fullmatch(self.record_sha256)):
            raise ValueError("invalid_regression_record_digest")


def summarize_regression_claims(
    claims: Sequence[RegressionRunClaim], *, expected_commit_sha: str,
) -> dict:
    """Validate coverage; never promote a supplied test claim to verified CI."""
    if type(expected_commit_sha) is not str or not _SHA40.fullmatch(expected_commit_sha):
        raise ValueError("invalid_expected_commit")
    if (not isinstance(claims, Sequence) or isinstance(claims, (str, bytes))
            or len(claims) > _MAX_RUNS):
        raise ValueError("invalid_regression_claims")
    by_key = {}
    for item in claims:
        if not isinstance(item, RegressionRunClaim):
            raise ValueError("invalid_regression_claim")
        key = item.environment + ":" + item.python_version
        if key in by_key:
            raise ValueError("duplicate_regression_matrix_key")
        by_key[key] = item
    missing = [x for x in _MISSING if x not in by_key]
    wrong_commit = sorted(k for k, r in by_key.items() if r.commit_sha != expected_commit_sha)
    reported_failures = sorted(k for k, r in by_key.items() if r.result != "passed")
    totals = {r.test_count for r in by_key.values()}
    mismatched_total = len(totals) > 1
    absent_digest = sorted(k for k, r in by_key.items() if r.record_sha256 is None)
    # Even a self-consistent record digest is untrusted without an external
    # signature and independently pinned identity. Never claim verification.
    claimed_complete = (not missing and not wrong_commit and not reported_failures
                        and not mismatched_total and not absent_digest)
    rows = [{"matrix_key": k, "commit_matches_expected": r.commit_sha == expected_commit_sha,
             "result_claim": r.result, "test_count": r.test_count,
             "skipped": r.skipped, "source_kind_claim": r.source_kind,
             "record_digest_supplied": r.record_sha256 is not None}
            for k, r in sorted(by_key.items())]
    report = {
        "required_matrix_keys": list(_MISSING),
        "reported_matrix_keys": sorted(by_key),
        "missing_matrix_keys": missing,
        "wrong_commit_matrix_keys": wrong_commit,
        "reported_failure_matrix_keys": reported_failures,
        "missing_record_digest_keys": absent_digest,
        "test_count_disagreement": mismatched_total,
        "coverage_complete_as_claimed": not missing,
        "all_results_passed_as_claimed": bool(by_key) and not reported_failures,
        "complete_consistent_matrix_as_claimed": claimed_complete,
        "runs": rows,
        "run_origin_authenticated": False,
        "device_identity_authenticated": False,
        "ci_attestations_verified": False,
        "approval_granted": False,
    }
    report["matrix_sha256"] = sha256(_canonical({"domain": "klone-v31-regression-matrix",
                                              "expected_commit_sha": expected_commit_sha,
                                              "claims": [
                                                  [k, by_key[k].commit_sha, by_key[k].test_count,
                                                   by_key[k].skipped, by_key[k].result,
                                                   by_key[k].source_kind, by_key[k].record_sha256]
                                                  for k in sorted(by_key)]})).hexdigest()
    return report


@dataclass(frozen=True)
class ProofRebuildInputs:
    """Explicit original inputs; the v2.9 report is always recomputed."""
    nodes: tuple
    tasks: tuple
    receipts: tuple
    request: object

    def __post_init__(self) -> None:
        if (type(self.nodes) is not tuple or type(self.tasks) is not tuple
                or type(self.receipts) is not tuple
                or len(self.nodes) > 512 or len(self.tasks) > 72
                or len(self.receipts) > 72):
            raise ValueError("invalid_proof_rebuild_inputs")


def build_mission_control_review(
    *, expected_commit_sha: str, domain_states: Mapping[str, str],
    memory_before: Sequence[PublicMemoryEvent],
    memory_after: Sequence[PublicMemoryEvent],
    regression_claims: Sequence[RegressionRunClaim] = (),
    proof_inputs: ProofRebuildInputs | None = None,
) -> dict:
    """Review-only, bounded, public-room dashboard data with explicit gaps.

    Recalculates memory and v2.9 claims from original inputs, not supplied
    status fragments. Does not read a live database or a connected service.
    """
    matrix = summarize_regression_claims(regression_claims, expected_commit_sha=expected_commit_sha)
    if not isinstance(domain_states, Mapping):
        raise ValueError("invalid_domain_states")
    # Feed full input to existing all-domains contract. Reject unknown keys,
    # don't treat missing domains as passed.
    pulse = build_system_review_pulse(
        domain_states=dict(domain_states), memory_before=memory_before,
        memory_after=memory_after,
    )
    proof_summary = {"provided": False, "recomputed_from_original_inputs": False,
                     "report_sha256": None, "review_status": "not_supplied",
                     "review_holds": [], "external_origin_verified": False,
                     "execution_authorized": False}
    if proof_inputs is not None:
        if not isinstance(proof_inputs, ProofRebuildInputs):
            raise ValueError("invalid_proof_rebuild_inputs")
        from .proof_carrying_cognition_v29 import build_review_proof
        proof = build_review_proof(
            proof_inputs.nodes, proof_inputs.tasks, proof_inputs.receipts,
            proof_inputs.request)
        proof_summary = {
            "provided": True, "recomputed_from_original_inputs": True,
            "report_sha256": proof["report_sha256"],
            "review_status": proof["review_status"],
            "review_holds": proof["review_holds"],
            "external_origin_verified": False, "execution_authorized": False,
        }
    reasons = set(pulse["blocking_review_reasons"])
    if matrix["missing_matrix_keys"]:
        reasons.add("regression_matrix_incomplete")
    if matrix["wrong_commit_matrix_keys"]:
        reasons.add("regression_commit_mismatch")
    if matrix["reported_failure_matrix_keys"]:
        reasons.add("regression_reported_failure")
    if matrix["test_count_disagreement"]:
        reasons.add("regression_total_count_disagreement")
    if matrix["missing_record_digest_keys"]:
        reasons.add("regression_report_digest_missing")
    if not proof_summary["provided"]:
        reasons.add("council_proof_not_supplied")
    elif proof_summary["review_holds"] or proof_summary["review_status"] != "unverified_packet_ready_for_manual_review":
        reasons.add("council_proof_requires_review")
    reasons.add("test_provenance_unverified")
    hard_hold = (pulse["memory_status"] == "blocked" or
                 bool(matrix["wrong_commit_matrix_keys"] or matrix["reported_failure_matrix_keys"] or
                      matrix["test_count_disagreement"]) or
                 (proof_summary["provided"] and
                  proof_summary["review_status"] == "hold_for_manual_review"))
    report = {
        "schema_version": 1, "kind": "klone-mission-control-observatory-v31-lab",
        "expected_commit_sha": expected_commit_sha,
        "domain_count": len(DOMAINS),
        "domain_states": pulse["domain_states"],
        "claimed_passed_domain_count": pulse["domain_checks_passed_claimed"],
        "memory_status": pulse["memory_status"],
        "memory_report_sha256": pulse["memory_report_sha256"],
        "system_pulse_sha256": pulse["pulse_sha256"],
        "regression": matrix,
        "council_proof": proof_summary,
        "review_reasons": sorted(reasons),
        "review_status": "blocked_for_review" if hard_hold else "manual_review_required",
        "report_sources_authenticated": False,
        "memory_snapshot_completeness_verified": False,
        "cross_room_data_loaded": False,
        "service_health_checked": False,
        "live_agent_telemetry_measured": False,
        "external_audit_anchor_verified": False,
        "permission_granted": False,
        "tasks_dispatched": False,
        "production_readiness_verified": False,
        "deployment_approval": False,
        "manual_review_required": True,
    }
    encoded = _canonical(report)
    if len(encoded) > _MAX_REPORT_BYTES - 256:
        raise ValueError("mission_control_report_too_large")
    report["report_sha256"] = sha256(_canonical({"domain": "klone-v31-mission-control",
                                                 "report": report})).hexdigest()
    return report


def verify_mission_control_review(
    reported: object, *, expected_commit_sha: str,
    domain_states: Mapping[str, str],
    memory_before: Sequence[PublicMemoryEvent],
    memory_after: Sequence[PublicMemoryEvent],
    regression_claims: Sequence[RegressionRunClaim] = (),
    proof_inputs: ProofRebuildInputs | None = None,
) -> bool:
    """Deterministic replay only; supplied bytes cannot authenticate origin."""
    if type(reported) is not dict:
        return False
    try:
        if len(_canonical(reported)) > _MAX_REPORT_BYTES:
            return False
        expected = build_mission_control_review(
            expected_commit_sha=expected_commit_sha, domain_states=domain_states,
            memory_before=memory_before, memory_after=memory_after,
            regression_claims=regression_claims, proof_inputs=proof_inputs)
        return hmac.compare_digest(_canonical(reported), _canonical(expected))
    except (ValueError, TypeError, OverflowError, RecursionError):
        return False
