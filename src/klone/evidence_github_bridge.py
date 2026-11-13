"""Read-only GitHub Actions status bridge using the official HTTPS API.

No credentials are persisted. Public repository access needs no token.
TLS validates transport, but does not cryptographically attest CI execution.
"""
from __future__ import annotations

import argparse
import http.client
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request

from klone.evidence_network import SHA
from klone.evidence_io import json_object, new_output_path, write_new_report

MAX_RESPONSE = 2 * 1024 * 1024
MAX_RUNS = 100
WORKFLOW = "KLONE regression guard"
WORKFLOW_PATH = ".github/workflows/klone-regression.yml"
REPOSITORY = "SickDinner/klone"
STATUSES = {"completed", "queued", "in_progress", "requested", "waiting", "pending"}
CONCLUSIONS = {"success", "failure", "cancelled", "timed_out", "action_required",
               "neutral", "skipped", "stale", "startup_failure", None}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("GitHub CI redirects are not allowed")


def normalize(payload: dict, expected_commit: str) -> dict:
    if not isinstance(expected_commit, str) or not SHA.fullmatch(expected_commit):
        raise ValueError("invalid expected commit")
    if not isinstance(payload, dict) or not isinstance(payload.get("workflow_runs"), list):
        raise ValueError("invalid GitHub API response")
    runs = payload["workflow_runs"]
    if (type(payload.get("total_count")) is not int or payload["total_count"] != len(runs)
            or len(runs) > MAX_RUNS or any(not isinstance(run, dict) for run in runs)):
        raise ValueError("invalid or truncated workflow listing")
    matching = [
        run for run in runs
        if run.get("head_sha") == expected_commit
        and run.get("name") == WORKFLOW
        and run.get("event") in ("push", "pull_request", "workflow_dispatch")
    ]
    if not matching:
        raise ValueError("no matching workflow run")
    for run in matching:
        if (type(run.get("id")) is not int or run["id"] < 1 or
                type(run.get("run_attempt")) is not int or run["run_attempt"] < 1 or
                not isinstance(run.get("repository"), dict) or
                run["repository"].get("full_name") != REPOSITORY or
                run.get("path") != WORKFLOW_PATH or
                not isinstance(run.get("status"), str) or run["status"] not in STATUSES or
                not (run.get("conclusion") is None or isinstance(run["conclusion"], str)) or
                run.get("conclusion") not in CONCLUSIONS):
            raise ValueError("invalid matching workflow identity or state")
    if len({run["id"] for run in matching}) != len(matching):
        raise ValueError("duplicate workflow run identity")
    matching.sort(key=lambda x: x["id"], reverse=True)
    run = matching[0]
    return {
        "schema_version": 1, "commit": expected_commit,
        "workflow": WORKFLOW, "workflow_path": WORKFLOW_PATH,
        "repository": REPOSITORY, "event": run["event"],
        "conclusion": run.get("conclusion") if run.get("status") == "completed" else None,
        "run_id": run["id"], "run_attempt": run["run_attempt"], "run_status": run["status"],
        "listing_complete": True, "job_matrix_verified": False,
        "source": "github_actions_api",
        "origin_authenticated": False, "deployment_approval": False,
    }


def fetch(repo: str, commit: str, token: str | None = None) -> dict:
    if repo != REPOSITORY:
        raise ValueError("repository must be SickDinner/klone")
    if not isinstance(commit, str) or not SHA.fullmatch(commit):
        raise ValueError("invalid commit")
    if token is not None and (not isinstance(token, str) or
                             (token and not re.fullmatch(r"[\x21-\x7e]{1,4096}", token))):
        raise ValueError("invalid GitHub token format")
    url = ("https://api.github.com/repos/SickDinner/klone/actions/runs"
           "?per_page=100&head_sha=" + commit)
    headers = {"Accept": "application/vnd.github+json",
               "User-Agent": "KLONE-Evidence-CI-Bridge/1"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(url, headers=headers)
    try:
        opener = urllib.request.build_opener(_NoRedirect())
        with opener.open(request, timeout=15) as response:
            raw = response.read(MAX_RESPONSE + 1)
        if len(raw) > MAX_RESPONSE:
            raise ValueError("GitHub CI response size limit exceeded")
        payload = json_object(raw)
    except (UnicodeError, RecursionError):
        raise ValueError("invalid GitHub CI JSON") from None
    except (http.client.HTTPException, OSError, urllib.error.URLError) as exc:
        raise ValueError("GitHub CI request failed: " + type(exc).__name__) from None
    return normalize(payload, commit)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--repo", default="SickDinner/klone")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--runs-root", type=Path, default=Path.home() / "klone-var/test-runs",
                        help="Protected historical evidence root; output must be outside it")
    parser.add_argument("--forensics-map", action="store_true", help="Export a commit-keyed Forensics input")
    args = parser.parse_args(argv)
    try:
        new_output_path(args.output, args.runs_root)
        result = fetch(args.repo, args.commit, os.environ.get("GITHUB_TOKEN"))
        exported = {args.commit: result} if args.forensics_map else result
        write_new_report(args.output, json.dumps(exported, sort_keys=True, indent=2) + "\n", args.runs_root)
    except (ValueError, OSError, urllib.error.URLError, UnicodeError, RecursionError) as exc:
        parser.error(str(exc))
    print(json.dumps({**result, "output": str(args.output)}, sort_keys=True, indent=2))
    return 0 if result["conclusion"] == "success" else 2


if __name__ == "__main__":
    raise SystemExit(main())
