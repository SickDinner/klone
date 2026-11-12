"""Offline unified KLONE quality gate.

No hardware identity claims, remote execution, or deployment side effects.
"""
from __future__ import annotations

from collections.abc import Mapping

from .acceptance_matrix import DOMAINS, summarize_acceptance
from .ci_attestation import attest_ci_payload
from .termux_evidence_consistency import review_pinned_termux_result


def evaluate_quality_gate(*, repository: str, commit: str,
                          ci_run: Mapping, ci_jobs: list[Mapping],
                          required_ci_jobs: set[str],
                          termux_report: Mapping | None = None,
                          domain_states: Mapping[str, str] | None = None) -> dict:
    ci = attest_ci_payload(
        ci_run, ci_jobs, repository=repository, expected_sha=commit,
        required_jobs=required_ci_jobs,
    )
    android = None
    if termux_report is not None:
        android = review_pinned_termux_result(
            termux_report, expected_commit=commit,
        )
    states = dict.fromkeys(DOMAINS, "unverified")
    states["ci"] = "passed"
    if android is not None:
        states["android"] = "passed"
    if domain_states is not None:
        if not isinstance(domain_states, Mapping):
            raise ValueError("invalid domain states")
        if set(domain_states) - set(DOMAINS):
            raise ValueError("unknown acceptance domain")
        if any(name in {"ci", "android", "deployment"} for name in domain_states):
            raise ValueError("reserved domain status cannot be overridden")
        states.update(domain_states)
    matrix = summarize_acceptance(states)
    return {
        "repository": repository,
        "commit": commit,
        "ci": ci,
        "android": android,
        "matrix": matrix,
        "ready_for_manual_review": bool(
            android is not None and all(
                states[name] == "passed" for name in DOMAINS
                if name != "deployment"
            )
        ),
        "deployment_approval": False,
    }
