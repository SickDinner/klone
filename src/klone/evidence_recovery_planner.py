"""Read-only recovery planning for incomplete historical evidence.

Never recreates evidence packets or edits historical runs.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from klone.evidence_quality import report
from klone.evidence_observatory import collect


def plan(runs_root: Path, runs: list[dict]) -> dict:
    root = runs_root.resolve()
    items = []
    for run in runs:
        if run.get("category") != "incomplete":
            continue
        name = run.get("run_name")
        if not isinstance(name, str) or not name or Path(name).name != name:
            raise ValueError("invalid run name")
        folder = runs_root / name
        if folder.is_symlink() or folder.resolve().parent != root:
            raise ValueError("unsafe run directory")
        has_run = (folder / "run.json").is_file() and not (folder / "run.json").is_symlink()
        has_packet = ((folder / "evidence-packet.json").is_file()
                      and not (folder / "evidence-packet.json").is_symlink())
        if has_run and not has_packet:
            category = "inspect_source_artifacts"
            advice = "Inspect original run manifest and artifacts; do not backfill historical packet."
        elif not has_run and not has_packet:
            category = "original_manifest_missing"
            advice = "Locate independently preserved original files; otherwise keep history incomplete."
        else:
            category = "investigate_invalid_or_mismatched_files"
            advice = "Inspect sizes, schema, hashes and errors read-only."
        items.append({"run_name": name, "run_json_present": has_run,
                      "evidence_packet_present": has_packet, "action": category,
                      "recommendation": advice, "historical_evidence_recreated": False})
    return {"schema_version": 1, "runs": items,
            "counts": {key: sum(x["action"] == key for x in items)
                       for key in ("inspect_source_artifacts",
                                   "original_manifest_missing",
                                   "investigate_invalid_or_mismatched_files")},
            "origin_authenticated": False, "deployment_approval": False}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        quality = report(collect(args.runs_root))
        result = plan(args.runs_root, quality["runs"])
        if args.output.is_symlink():
            raise ValueError("refusing symlink output")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n",
                               encoding="utf-8")
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps({"counts": result["counts"], "runs": len(result["runs"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
