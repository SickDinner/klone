"""Independent read-only reviewers of an evidence cross-check report.

Reviewers provide competing explanations, not fixes or permissions.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def review(report: dict) -> dict:
    local = report.get("local") if isinstance(report.get("local"), dict) else {}
    remote = report.get("github") if isinstance(report.get("github"), dict) else {}
    comparison = report.get("comparison") if isinstance(report.get("comparison"), dict) else {}
    integrity = local.get("integrity_ok") is True
    stages = local.get("required_stages_passed") is True
    same_commit = bool(local.get("commit")) and local.get("commit") == remote.get("commit")
    ci = remote.get("conclusion") == "success"
    reviewers = [
        {"role": "integrity_skeptic", "supports": integrity,
         "finding": "Local files match the checked manifest" if integrity else "Local integrity not established"},
        {"role": "regression_skeptic", "supports": stages,
         "finding": "Required local stages passed" if stages else "Required local stages not proven passed"},
        {"role": "environment_skeptic", "supports": same_commit and ci,
         "finding": "CI reports success for matching commit" if same_commit and ci else "Cross-environment CI claim missing or mismatched"},
        {"role": "adversarial_reviewer", "supports": False,
         "finding": "Unauthenticated CI export and local device identity cannot establish provenance"},
    ]
    all_operational = integrity and stages and same_commit and ci and comparison.get("consistent_claims") is True
    return {
        "schema_version": 1, "reviewers": reviewers,
        "operational_claims_consistent": all_operational,
        "unresolved_questions": [
            "Who authenticated the GitHub API response and runner identity?",
            "Who authenticated the Android device and local execution?",
            "Can the same commit be reproduced in a clean isolated environment?",
        ],
        "decision": "manual_review_required" if all_operational else "blocked",
        "origin_authenticated": False, "deployment_approval": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.report.stat().st_size > 1024 * 1024:
            raise ValueError("report too large")
        report = json.loads(args.report.read_text(encoding="utf-8"))
        if not isinstance(report, dict):
            raise ValueError("report must be an object")
    except (OSError, ValueError, UnicodeError) as exc:
        parser.error(str(exc))
    result = review(report)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["decision"] == "manual_review_required" else 2


if __name__ == "__main__":
    raise SystemExit(main())
