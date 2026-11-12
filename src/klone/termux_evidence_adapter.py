"""Conservative offline normalization of KLONE Termux bridge result comments.

A comment is not authenticated device evidence. The caller must independently
verify issue author, comment author, repository and expected commit.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from .test_evidence_ledger import validate


def normalize_termux_comment(comment: str, *, action: str, issue_number: int,
                             expected_commit: str, observed_at: str | None = None) -> dict:
    if action not in {"tests", "health", "git_status", "status"}:
        raise ValueError("unsupported bridge action")
    if not isinstance(issue_number, int) or isinstance(issue_number, bool) or issue_number < 1:
        raise ValueError("invalid issue number")
    if not isinstance(comment, str) or len(comment) > 15000:
        raise ValueError("invalid comment")
    prefix = "KLONE Termux bridge result for `" + action + "`"
    if not comment.startswith(prefix + "\n"):
        raise ValueError("unexpected bridge comment")
    codes = re.findall(r"^Exit code: (\d+)$", comment, re.MULTILINE)
    if len(codes) != 1:
        raise ValueError("missing or ambiguous exit code")
    exit_code = int(codes[0])
    if action == "tests":
        tests = re.search(r"^Tests: (\d+) in ([\d.]+)s; (OK(?: \(skipped=\d+\))?|FAILED \(.*\))$",
                          comment, re.MULTILINE)
        if not tests:
            raise ValueError("test summary missing")
        verdict = tests.group(3)
        status = "success" if exit_code == 0 and verdict.startswith("OK") else "failure"
        if exit_code == 0 and not verdict.startswith("OK"):
            raise ValueError("conflicting test summary")
        details = {"action": action, "tests": int(tests.group(1)), "verdict": verdict}
    else:
        status = "success" if exit_code == 0 else "failure"
        details = {"action": action}
    timestamp = observed_at or datetime.now(timezone.utc).isoformat()
    return validate({
        "source": "termux_bridge", "run_id": f"issue-{issue_number}-{action}",
        "commit": expected_commit, "status": status, "observed_at": timestamp,
        "environment": "android-termux", "details": details,
    })
