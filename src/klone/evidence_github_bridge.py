"""Read-only GitHub Actions status bridge using the official HTTPS API.

No credentials are persisted. Public repository access needs no token.
TLS validates transport, but does not cryptographically attest CI execution.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

from klone.evidence_network import SHA


def normalize(payload: dict, expected_commit: str) -> dict:
    if not isinstance(expected_commit, str) or not SHA.fullmatch(expected_commit):
        raise ValueError("invalid expected commit")
    if not isinstance(payload, dict) or not isinstance(payload.get("workflow_runs"), list):
        raise ValueError("invalid GitHub API response")
    matching = [
        run for run in payload["workflow_runs"]
        if isinstance(run, dict)
        and run.get("head_sha") == expected_commit
        and run.get("name") == "KLONE regression guard"
        and run.get("event") in ("push", "pull_request", "workflow_dispatch")
    ]
    if not matching:
        raise ValueError("no matching workflow run")
    matching.sort(key=lambda x: x.get("id", 0) if isinstance(x.get("id"), int) else 0,
                  reverse=True)
    run = matching[0]
    return {
        "schema_version": 1, "commit": expected_commit,
        "workflow": "KLONE regression guard",
        "conclusion": run.get("conclusion") if run.get("status") == "completed" else None,
        "run_id": run.get("id"), "run_status": run.get("status"),
        "source": "github_actions_api",
        "origin_authenticated": False, "deployment_approval": False,
    }


def fetch(repo: str, commit: str, token: str | None = None) -> dict:
    if repo != "SickDinner/klone":
        raise ValueError("repository must be SickDinner/klone")
    if not SHA.fullmatch(commit):
        raise ValueError("invalid commit")
    url = ("https://api.github.com/repos/SickDinner/klone/actions/runs"
           "?per_page=100&head_sha=" + commit)
    headers = {"Accept": "application/vnd.github+json",
               "User-Agent": "KLONE-Evidence-CI-Bridge/1"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = json.load(response)
    return normalize(payload, commit)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--repo", default="SickDinner/klone")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = fetch(args.repo, args.commit, os.environ.get("GITHUB_TOKEN"))
    except (ValueError, OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps({**result, "output": str(args.output)}, sort_keys=True, indent=2))
    return 0 if result["conclusion"] == "success" else 2


if __name__ == "__main__":
    raise SystemExit(main())
