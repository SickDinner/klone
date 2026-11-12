"""Fail-closed GitHub Actions run verification, offline and deterministic.

Input must originate from an authenticated GitHub API response. This module
does not fetch data, authenticate requests or establish device provenance.
"""
from __future__ import annotations

from collections.abc import Mapping


def verify_ci_run(run: Mapping, jobs: list[Mapping], *,
                  repository: str, expected_sha: str,
                  required_jobs: set[str]) -> dict:
    if not isinstance(run, Mapping) or not isinstance(jobs, list):
        raise ValueError("invalid GitHub API payload")
    if not repository or not required_jobs or not isinstance(required_jobs, set):
        raise ValueError("repository and required jobs must be explicit")
    if not isinstance(expected_sha, str) or len(expected_sha) != 40 or any(
        c not in "0123456789abcdef" for c in expected_sha
    ):
        raise ValueError("full lowercase commit SHA required")
    repo = run.get("repository")
    if not isinstance(repo, Mapping) or repo.get("full_name") != repository:
        raise ValueError("repository mismatch")
    if run.get("head_sha") != expected_sha:
        raise ValueError("commit mismatch")
    if run.get("status") != "completed" or run.get("conclusion") != "success":
        raise ValueError("CI workflow not successful")
    run_id = run.get("id")
    attempt = run.get("run_attempt")
    if type(run_id) is not int or run_id < 1 or type(attempt) is not int or attempt < 1:
        raise ValueError("invalid run identity")
    names = set()
    for job in jobs:
        if not isinstance(job, Mapping) or job.get("run_id") != run_id:
            raise ValueError("job does not belong to verified run")
        name = job.get("name")
        if not isinstance(name, str) or not name or name in names:
            raise ValueError("duplicate or invalid job name")
        names.add(name)
        if job.get("status") != "completed" or job.get("conclusion") != "success":
            raise ValueError("job not successful")
    if not required_jobs.issubset(names):
        raise ValueError("required jobs missing")
    return {
        "repository": repository,
        "commit": expected_sha,
        "run_id": str(run_id),
        "run_attempt": attempt,
        "jobs": sorted(names),
        "required_jobs": sorted(required_jobs),
        "verified_success": True,
        "provenance": "caller_authenticated_github_api",
    }
