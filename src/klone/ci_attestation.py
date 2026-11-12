"""Read-only CI attestation composition; never authorizes deployment."""
from __future__ import annotations

from collections.abc import Mapping

from .ci_run_gate import verify_ci_run


def attest_ci_payload(run: Mapping, jobs: list[Mapping], *,
                      repository: str, expected_sha: str,
                      required_jobs: set[str]) -> dict:
    verified = verify_ci_run(
        run, jobs, repository=repository, expected_sha=expected_sha,
        required_jobs=required_jobs,
    )
    return {
        "commit": verified["commit"],
        "repository": verified["repository"],
        "run_id": verified["run_id"],
        "run_attempt": verified["run_attempt"],
        "verified_jobs": verified["jobs"],
        "required_jobs": verified["required_jobs"],
        "ci_consistency": "passed",
        "android_attestation": "not_verified",
        "memory_audit_attestation": "not_verified",
        "deployment_approval": False,
        "manual_review_required": True,
    }
