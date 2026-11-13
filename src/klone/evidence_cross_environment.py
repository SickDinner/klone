"""Offline comparison of Android and GitHub CI evidence claims.

Inputs are untrusted exported JSON. This module checks consistency only,
not origin, signature validity or runner identity.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from klone.evidence_network import SHA, REQUIRED
from klone.evidence_io import json_object, read_bounded, new_output_path, write_new_report


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
    if "run_status" in github and github["run_status"] != "completed":
        errors.append("github_ci_not_completed")
    if "listing_complete" in github and github["listing_complete"] is not True:
        errors.append("github_ci_listing_incomplete")
    if "repository" in github and github["repository"] != "SickDinner/klone":
        errors.append("unexpected_repository")
    if "workflow_path" in github and github["workflow_path"] != ".github/workflows/klone-regression.yml":
        errors.append("unexpected_workflow_path")
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
    parser.add_argument("--runs-root", type=Path, default=Path.home() / "klone-var/test-runs")
    args = parser.parse_args(argv)
    try:
        if args.output:
            new_output_path(args.output, args.runs_root)
        result = compare(json_object(read_bounded(args.android_status, 131072)),
                         json_object(read_bounded(args.github_ci, 131072)))
        rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
        if args.output:
            write_new_report(args.output, rendered, args.runs_root)
    except (ValueError, OSError, TypeError, KeyError, UnicodeError, RecursionError) as exc:
        parser.error(str(exc))
    print(rendered, end="")
    return 0 if result["consistent_claims"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
