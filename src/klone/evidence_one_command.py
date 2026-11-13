"""One-command, read-only cross-environment evidence report.

Never changes git state, uploads logs, or grants deployment approval.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import urllib.error

from klone.evidence_status import inspect
from klone.evidence_github_bridge import fetch
from klone.evidence_cross_environment import compare
from klone.evidence_io import new_output_path, write_new_report


def run(run_directory: Path, packet: Path, *, github_fetch=fetch) -> dict:
    local = inspect(run_directory, packet)
    if not local["integrity_ok"] or not local["required_stages_passed"]:
        return {"schema_version": 1, "local": local, "github": None,
                "comparison": None, "decision": "blocked",
                "errors": ["local_evidence_invalid"],
                "origin_authenticated": False, "deployment_approval": False}
    try:
        remote = github_fetch("SickDinner/klone", local["commit"],
                              os.environ.get("GITHUB_TOKEN"))
    except (ValueError, OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        return {"schema_version": 1, "local": local, "github": None,
                "comparison": None, "decision": "blocked",
                "errors": ["github_ci_unavailable:" + type(exc).__name__],
                "origin_authenticated": False, "deployment_approval": False}
    comparison = compare(local, remote)
    return {"schema_version": 1, "local": local, "github": remote,
            "comparison": comparison, "decision": comparison["decision"],
            "errors": comparison["errors"], "origin_authenticated": False,
            "deployment_approval": False}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-directory", type=Path, required=True)
    parser.add_argument("--packet", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    packet = args.packet or args.run_directory / "evidence-packet.json"
    try:
        if args.output:
            new_output_path(args.output, args.run_directory.parent)
        result = run(args.run_directory, packet)
        rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
        if args.output:
            write_new_report(args.output, rendered, args.run_directory.parent)
    except (ValueError, OSError, TypeError, UnicodeError, RecursionError) as exc:
        parser.error(str(exc))
    print(rendered, end="")
    return 0 if result["decision"] == "manual_review_required" else 2


if __name__ == "__main__":
    raise SystemExit(main())
