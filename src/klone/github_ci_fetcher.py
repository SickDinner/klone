"""Authenticated, bounded read-only GitHub CI API fetcher.

No secrets are written to files or returned in error messages.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request


REPO_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def fetch_ci_run_and_jobs(repository: str, run_id: int, *,
                          token: str | None = None,
                          opener=None) -> tuple[dict, list[dict]]:
    if (not isinstance(repository, str) or not REPO_PATTERN.fullmatch(repository)\n            or any(part in {".", ".."} for part in repository.split("/"))):
        raise ValueError("invalid repository")
    if type(run_id) is not int or run_id < 1:
        raise ValueError("invalid run ID")
    secret = token if token is not None else os.environ.get("GITHUB_TOKEN", "")
    if not isinstance(secret, str) or not secret.strip():
        raise ValueError("GitHub token required")
    opener = opener or urllib.request.urlopen

    def get(path: str):
        req = urllib.request.Request(
            "https://api.github.com/repos/" + repository + path,
            headers={
                "Authorization": "Bearer " + secret,
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "klone-ci-evidence",
            },
        )
        try:
            with opener(req, timeout=15) as response:
                payload = response.read(1024 * 1024 + 1)
        except Exception as exc:
            # Avoid embedding HTTP response headers, token or request URL in logs.
            raise RuntimeError("GitHub API request failed") from None
        if len(payload) > 1024 * 1024:
            raise ValueError("GitHub response exceeds limit")
        try:
            return json.loads(payload)
        except (ValueError, UnicodeDecodeError):
            raise ValueError("invalid GitHub response JSON") from None

    run = get(f"/actions/runs/{run_id}")
    if not isinstance(run, dict) or run.get("id") != run_id:
        raise ValueError("GitHub run identity mismatch")
    jobs_payload = get(f"/actions/runs/{run_id}/jobs?per_page=100&page=1")
    if not isinstance(jobs_payload, dict) or type(jobs_payload.get("total_count")) is not int:
        raise ValueError("invalid GitHub jobs response")
    jobs = jobs_payload.get("jobs")
    if not isinstance(jobs, list) or jobs_payload["total_count"] != len(jobs):
        raise ValueError("incomplete CI job listing; pagination required")
    return run, jobs
