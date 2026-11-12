"""Bind KLONE acceptance claims to deterministic evidence manifests.

A source/reference is a traceable claim, not independently authenticated proof.
"""
from __future__ import annotations

from collections.abc import Mapping

from .acceptance_matrix import DOMAINS
from .quality_evidence_manifest import fingerprint_evidence
from .unified_quality_gate import evaluate_quality_gate


def evaluate_evidence_bound_review(
    *, repository: str, commit: str, ci_run: Mapping,
    ci_jobs: list[Mapping], required_ci_jobs: set[str],
    domain_evidence: Mapping, termux_report: Mapping | None = None,
) -> dict:
    manifest = fingerprint_evidence(
        commit=commit, domain_evidence=domain_evidence,
    )
    states = {name: manifest["domains"][name]["state"] for name in DOMAINS}
    if states["ci"] != "passed":
        raise ValueError("CI evidence must explicitly be passed")
    if states["deployment"] == "passed":
        raise ValueError("deployment cannot self-attest approval")
    if states["android"] == "passed" and termux_report is None:
        raise ValueError("Android passed without pinned test report")
    if termux_report is not None and states["android"] != "passed":
        raise ValueError("Android report/state mismatch")
    ci_ref = manifest["domains"]["ci"]["reference"]
    expected_run_id = ci_run.get("id")
    if type(expected_run_id) is not int or ci_ref != f"run:{expected_run_id}":
        raise ValueError("CI evidence run reference mismatch")
    states.pop("ci")
    states.pop("android")
    states.pop("deployment")
    review = evaluate_quality_gate(
        repository=repository, commit=commit, ci_run=ci_run,
        ci_jobs=ci_jobs, required_ci_jobs=required_ci_jobs,
        termux_report=termux_report, domain_states=states,
    )
    return {
        "schema_version": 1,
        "repository": repository,
        "commit": commit,
        "manifest_sha256": manifest["sha256"],
        "review": review,
        "evidence_authenticated": False,
        "device_identity_verified": False,
        "deployment_approval": False,
        "manual_review_required": True,
    }
