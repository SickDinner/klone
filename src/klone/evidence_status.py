"""Offline, read-only KLONE evidence status report.

Usage: python -m klone.evidence_status --run-directory DIR --packet PACKET
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from klone.evidence_network import _read_json, build_packet, REQUIRED, STAGES


def inspect(run_directory: Path, packet_path: Path) -> dict:
    errors = []
    packet = None
    actual = None
    try:
        packet = _read_json(packet_path, 1024 * 1024)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        errors.append("packet_unreadable: " + str(exc))
    try:
        actual = build_packet(run_directory)
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as exc:
        errors.append("run_invalid: " + str(exc))
    if actual is not None and packet is not None and actual != packet:
        errors.append("packet_mismatch")
    integrity_ok = not errors
    stages = actual["stages"] if actual is not None else {}
    return {
        "schema_version": 1,
        "commit": actual["commit"] if actual is not None else None,
        "packet_sha256": actual["packet_sha256"] if actual is not None else None,
        "integrity_ok": integrity_ok,
        "required_stages_passed": all(stages.get(n) == "passed" for n in REQUIRED),
        "stage_statuses": {name: stages.get(name, "unknown") for name in STAGES},
        "errors": errors,
        "origin_authenticated": False,
        "deployment_approval": False,
        "decision": "manual_review_required" if integrity_ok and all(
            stages.get(n) == "passed" for n in REQUIRED) else "blocked",
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
