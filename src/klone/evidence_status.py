"""Offline, read-only KLONE evidence status report.

Usage: python -m klone.evidence_status --run-directory DIR --packet PACKET
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from klone.evidence_artifact_inspector import snapshot
from klone.evidence_io import json_object, read_bounded
from klone.evidence_network import assemble_packet, REQUIRED, STAGES


def inspect(run_directory: Path, packet_path: Path) -> dict:
    errors = []
    packet = None
    actual = None
    run = None
    try:
        packet = json_object(read_bounded(packet_path, 1024 * 1024))
    except (ValueError, OSError, UnicodeError, RecursionError) as exc:
        errors.append("packet_unreadable: " + str(exc))
    try:
        inventory, contents = snapshot(run_directory)
        if not inventory["manifest_valid"] or len(contents) != len(STAGES) + 1:
            raise ValueError("bounded source snapshot incomplete or invalid")
        run = json_object(contents["run.json"])
        files = {n + ".log": {k: inventory["artifacts"][n + ".log"][k] for k in ("bytes", "sha256")} for n in STAGES}
        actual = assemble_packet(run, inventory["artifacts"]["run.json"]["sha256"], files)
    except (ValueError, KeyError, TypeError, AttributeError, OSError, UnicodeError, RecursionError) as exc:
        errors.append("run_invalid: " + str(exc))
    if actual is not None and packet is not None and actual != packet:
        errors.append("packet_mismatch")
    integrity_ok = not errors
    stages = actual["stages"] if actual is not None else {}
    execution = run.get("execution") if actual is not None and run["schema_version"] == 2 else None
    context_ok = execution is None or (execution["context_consistent"] and run["collection_complete"])
    reported_passed = all(stages.get(n) == "passed" for n in REQUIRED)
    return {
        "schema_version": 1,
        "commit": actual["commit"] if actual is not None else None,
        "packet_sha256": actual["packet_sha256"] if actual is not None else None,
        "integrity_ok": integrity_ok,
        "manifest_schema_version": run["schema_version"] if actual is not None else None,
        "execution_context_id": execution["comparison_id"] if execution else None,
        "execution_context_consistent": execution["context_consistent"] if execution else None,
        "collection_complete": run["collection_complete"] if execution else None,
        "manifest_required_stages_passed": reported_passed,
        "required_stages_passed": reported_passed and context_ok,
        "stage_statuses": {name: stages.get(name, "unknown") for name in STAGES},
        "errors": errors,
        "origin_authenticated": False,
        "deployment_approval": False,
        "decision": "manual_review_required" if integrity_ok and reported_passed and context_ok else "blocked",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-directory", required=True, type=Path)
    parser.add_argument("--packet", required=True, type=Path)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args(argv)
    result = inspect(args.run_directory, args.packet)
    rendered = json.dumps(result, sort_keys=True, indent=2) + "\n"
    if args.json_output is not None:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["decision"] == "manual_review_required" else 2


if __name__ == "__main__":
    raise SystemExit(main())
