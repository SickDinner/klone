"""KLONE v3.0: read-only fail-closed review pulse across all 12 domains.

Reports gaps and provenance limitations; never claims service health, remote
attestation, authority or deployment readiness from caller-supplied booleans.
"""
from __future__ import annotations

from collections.abc import Sequence
from hashlib import sha256
import json

from .acceptance_matrix import DOMAINS, summarize_acceptance
from .memory_continuity_v30 import PublicMemoryEvent, check_memory_continuity


def build_system_review_pulse(
    *, domain_states: dict[str, str],
    memory_before: Sequence[PublicMemoryEvent],
    memory_after: Sequence[PublicMemoryEvent],
) -> dict:
    """Recheck memory, evaluate explicit domain claims, list blocked capabilities."""
    matrix = summarize_acceptance(domain_states)
    continuity = check_memory_continuity(memory_before, memory_after)
    issues = list("domain:" + x for x in matrix["blocked_domains"])
    if continuity["continuity_status"] == "blocked":
        issues.append("memory_continuity_conflict")
    # Even all passed caller declarations cannot authenticate an independent
    # external source, Android OS UID, key signer, or authoritative owner grant.
    issues += ["runtime_identity_unverified", "external_provenance_unverified",
               "independent_audit_anchor_unverified", "production_approval_absent"]
    pulse = {"schema_version": 1,
             "kind": "klone-system-readiness-pulse-v30-lab",
             "domain_count": len(DOMAINS),
             "domain_state_source": "caller_declared_not_authenticated",
             "domain_states": matrix["domains"],
             "domain_checks_passed_claimed": matrix["passed_count"],
             "memory_report_sha256": continuity["report_sha256"],
             "memory_status": continuity["continuity_status"],
             "blocking_review_reasons": sorted(issues),
             "review_status": "blocked" if continuity["continuity_status"] == "blocked"
                         else "manual_review_only",
             "service_health_checked": False,
             "cross_room_data_loaded": False,
             "proof_origin_authenticated": False,
             "permission_granted": False,
             "tasks_dispatched": False,
             "production_readiness_verified": False,
             "deployment_approval": False,
             "manual_review_required": True}
    pulse["pulse_sha256"] = sha256(json.dumps(pulse, ensure_ascii=True,
        sort_keys=True, allow_nan=False, separators=(",", ":")).encode("ascii")).hexdigest()
    return pulse
