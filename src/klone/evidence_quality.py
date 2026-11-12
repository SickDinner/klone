"""Read-only evidence quality taxonomy; never repairs or approves evidence."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from klone.evidence_observatory import collect, compare_history

CATEGORIES = ("verified", "incomplete", "contradictory", "unexamined")


def classify(run: dict) -> dict:
    errors = run.get("errors") or []
    if not isinstance(errors, list):
        errors = ["invalid_error_list"]
    if any(error == "packet_mismatch" for error in errors):
        category = "contradictory"
        reason = "packet_mismatch"
    elif any(isinstance(error, str) and
             (error.startswith("packet_unreadable:") or error.startswith("run_invalid:"))
             for error in errors):
        category = "incomplete"
        reason = "unreadable_or_missing_evidence"
    elif run.get("integrity_ok") is True and not errors:
        category = "verified"
        reason = ("required_stages_passed" if run.get("required_stages_passed") is True
                  else "verified_evidence_with_nonpassing_stages")
    else:
        category = "unexamined"
        reason = "insufficient_or_unrecognized_evidence"
    return {"run_name": run.get("run_name"), "commit": run.get("commit"),
            "category": category, "reason": reason,
            "required_stages_passed": run.get("required_stages_passed") is True,
            "integrity_ok": run.get("integrity_ok") is True,
            "errors": errors, "origin_authenticated": False,
            "deployment_approval": False}


def report(runs: list[dict]) -> dict:
    entries = [classify(run) for run in runs]
    counts = Counter(entry["category"] for entry in entries)
    comparisons = compare_history(runs)
    return {"schema_version": 1,
            "categories": {category: counts[category] for category in CATEGORIES},
            "runs": entries,
            "confirmed_regression_transitions": sum(
                len(c["regressed_stages"]) for c in comparisons),
            "unknown_transition_count": sum(
                len(c["unknown_transitions"]) for c in comparisons),
            "comparisons": comparisons,
            "origin_authenticated": False, "deployment_approval": False,
            "note": "Verified means local file integrity only; not authenticated provenance."}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = report(collect(args.runs_root))
        if args.output.is_symlink():
            raise ValueError("output must not be a symlink")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                               encoding="utf-8")
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({"categories": result["categories"],
                      "confirmed_regression_transitions": result["confirmed_regression_transitions"],
                      "unknown_transition_count": result["unknown_transition_count"]},
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
