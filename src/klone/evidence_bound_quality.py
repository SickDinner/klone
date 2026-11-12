"""Bind KLONE quality results to explicit, deterministic evidence references."""
from __future__ import annotations

from collections.abc import Mapping

from .acceptance_matrix import DOMAINS
from .quality_evidence_manifest import fingerprint_evidence
from .unified_quality_gate import evaluate_quality_gate


def evaluate_evidence_bound_quality(*, repository: str, commit: str,
                                    ci_run: Mapping, ci_jobs: list[Mapping],
                                    required_ci_jobs: set[str],
                                    evidence: Mapping,
                                    termux_report: Mapping | None = None) -> dict:
    manifest = fingerprint_evidence(commit=commit, domain_evidence=evidence)
    states = {domain: manifest["domains"][domain]["state"] for domain in DOMAINS}
    if states["deployment"] != "unverified":
        raise ValueError("deployment status is reserved")
    if states["ci"] != "passed":
        raise ValueError("CI must have passing evidence")
    if termux_report is None:
        if states["android"] != "unverified":
            raise ValueError("Android evidence without pinned report")
    elif states["android"] != "passed":
        raise ValueError("pinned Android report requires passing evidence")
    result = evaluate_quality_gate(
        repository=repository, commit=commit,
        ci_run=ci_run, ci_jobs=ci_jobs,
        required_ci_jobs=required_ci_jobs,
        termux_report=termux_report,
        domain_states={domain: states[domain] for domain in DOMAINS
                       if domain not in {"ci", "android", "deployment"}},
    )
    return {
        **result,
        "evidence_manifest": manifest,
        "evidence_fingerprint": manifest["sha256"],
        "source_authentication": "not_verified",
        "deployment_approval": False,
    }
