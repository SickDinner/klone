"""Deterministic, read-only evidence claims ledger.

Separates direct observations, unverified assumptions and open questions.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def ledger(report: dict) -> dict:
    if not isinstance(report, dict):
        raise ValueError("report must be an object")
    local = report.get("local") if isinstance(report.get("local"), dict) else {}
    github = report.get("github") if isinstance(report.get("github"), dict) else {}
    comparison = report.get("comparison") if isinstance(report.get("comparison"), dict) else {}
    observations = []
    for key in ("commit", "integrity_ok", "required_stages_passed"):
        if key in local:
            observations.append({"source": "local_report", "field": key,
                                 "value": local[key], "verified_origin": False})
    for key in ("commit", "conclusion", "run_id"):
        if key in github:
            observations.append({"source": "github_export", "field": key,
                                 "value": github[key], "verified_origin": False})
    claims_consistent = comparison.get("consistent_claims") is True
    return {
        "schema_version": 1,
        "observations": observations,
        "assumptions": [
            "Local evidence report reflects execution on the claimed device",
            "GitHub CI export reflects the official workflow execution",
            "A passing test suite covers all relevant failure modes",
        ],
        "open_questions": [
            "Can runner and device identity be independently authenticated?",
            "Is a trusted external digest anchor available?",
            "What changes remain untested?",
        ],
        "cross_environment_claims_consistent": claims_consistent,
        "decision": "manual_review_required" if claims_consistent else "blocked",
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
        result = ledger(report)
    except (OSError, ValueError, UnicodeError) as exc:
        parser.error(str(exc))
    output = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    print(output, end="")
    return 0 if result["decision"] == "manual_review_required" else 2


if __name__ == "__main__":
    raise SystemExit(main())
