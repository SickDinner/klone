"""Offline comparison of Android and GitHub CI evidence claims.

Inputs are untrusted exported JSON. This module checks consistency only,
not origin, signature validity or runner identity.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from klone.evidence_network import SHA, REQUIRED, _read_json


def compare(android: dict, github: dict) -> dict:
    errors = []
    a_commit = android.get("commit")
    g_commit = github.get("commit")
    if not isinstance(a_commit, str) or not SHA.fullmatch(a_commit):
        errors.append("invalid_android_commit")
    if not isinstance(g_commit, str) or not SHA.fullmatch(g_commit):
        errors.append("invalid_github_commit")
    if a_commit != g_commit:
        errors.append("commit_mismatch")
    if android.get("integrity_ok") is not True:
        errors.append("android_integrity_unverified")
    if android.get("required_stages_passed") is not True:
        errors.append("android_tests_not_passed")
    if github.get("conclusion") != "success":
        errors.append("github_ci_not_success")
    if github.get("workflow") != "KLONE regression guard":
        errors.append("unexpected_workflow")
    stages = android.get("stage_statuses")
    if not isinstance(stages, dict) or any(stages.get(x) != "passed" for x in REQUIRED):
        errors.append("android_required_stage_mismatch")
    return {
        "schema_version": 1, "android_commit": a_commit, "github_commit": g_commit,
        "consistent_claims": not errors, "errors": errors,
        "decision": "manual_review_required" if not errors else "blocked",
        "origin_authenticated": False, "deployment_approval": False,
        "note": "GitHub JSON must be independently authenticated; matching claims are not proof of origin.",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--android-status", type=Path, required=True)
    parser.add_argument("--github-ci", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        result = compare(_read_json(args.android_status),
                         _read_json(args.github_ci))
    except (ValueError, OSError, TypeError, KeyError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["consistent_claims"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
