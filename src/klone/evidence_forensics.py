"""Read-only, bounded cross-view evidence forensics. Never authenticates origin."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from klone.evidence_artifact_inspector import inspect as inspect_artifacts
from klone.evidence_io import checked_path, output_path, write_report
from klone.evidence_observatory import collect
from klone.evidence_quality import report as quality_report
from klone.evidence_recovery_planner import plan as recovery_plan


def analyze(runs_root: Path) -> dict:
    root = checked_path(runs_root, directory=True)
    quality = quality_report(collect(root))
    recovery = recovery_plan(root, quality["runs"])
    inspected = {}
    for directory in sorted(root.iterdir()):
        if directory.is_symlink() or not directory.is_dir():
            continue
        inspected[directory.name] = inspect_artifacts(directory)
    quality_by_name = {entry["run_name"]: entry for entry in quality["runs"]}
    recovery_by_name = {entry["run_name"]: entry for entry in recovery["runs"]}
    entries = []
    for name, artifact in inspected.items():
        status = quality_by_name.get(name)
        if status is None:
            raise ValueError("missing quality classification for run")
        findings = list(artifact["errors"])
        if not artifact["manifest_valid"]:
            findings.append("manifest_not_validated")
        if status["category"] != "verified":
            findings.append("quality_" + status["category"])
        entries.append({
            "run_name": name,
            "quality": status,
            "artifacts": artifact,
            "recovery": recovery_by_name.get(name),
            "findings": sorted(set(findings)),
            "requires_manual_review": True,
            "origin_authenticated": False,
            "deployment_approval": False,
        })
    return {
        "schema_version": 1,
        "runs": entries,
        "categories": quality["categories"],
        "comparisons": quality["comparisons"],
        "origin_authenticated": False,
        "deployment_approval": False,
        "note": "Current artifact hashes do not prove historical origin; no evidence is repaired or upgraded.",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        root = checked_path(args.runs_root, directory=True)
        output_path(args.output, root)
        result = analyze(root)
        write_report(args.output, json.dumps(result, sort_keys=True, indent=2) + "\n", root)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({"runs": len(result["runs"]), "categories": result["categories"]},
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
