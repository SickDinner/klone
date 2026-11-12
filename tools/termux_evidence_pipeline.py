"""Import a provenance-bearing Termux run.json and refresh an offline dashboard.

Never authenticates a device, verifies a signature or approves deployment.
Use --run to execute the battery first, or --run-directory to import an existing run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from klone.test_evidence_ledger import EvidenceLedger
from klone.test_evidence_dashboard import compare_commits, summarize
from test_evidence_dashboard import render
from termux_evidence_battery import run_battery

SHA = re.compile(r"^[0-9a-f]{40}$")
REQUIRED = ("syntax", "cognition", "full", "local_deploy")
OPTIONAL = ("passed", "failed", "unavailable", "not_present")


def load_report(directory: Path) -> dict:
    path = directory / "run.json"
    if not path.is_file() or path.stat().st_size > 65536:
        raise ValueError("missing or oversized run.json")
    report = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(report, dict) or report.get("schema_version") != 1:
        raise ValueError("unsupported report schema")
    before, after = report["before"], report["after"]
    if not all(isinstance(part, dict) for part in (before, after)):
        raise ValueError("invalid checkout")
    commit = before.get("commit")
    if not isinstance(commit, str) or not SHA.fullmatch(commit):
        raise ValueError("invalid recorded commit")
    if after.get("commit") != commit:
        raise ValueError("checkout commit changed")
    stages = report["stages"]
    if not isinstance(stages, dict) or set(stages) != set(REQUIRED) | {"torch_probe"}:
        raise ValueError("invalid stages")
    for name in REQUIRED:
        stage = stages[name]
        if not isinstance(stage, dict) or stage.get("status") not in ("passed", "failed"):
            raise ValueError("invalid required stage")
        if (stage["status"] == "passed") != (stage.get("exit_code") == 0):
            raise ValueError("contradictory required stage")
        if not (directory / (name + ".log")).is_file():
            raise ValueError("missing required log: " + name)
    torch = stages["torch_probe"]
    if not isinstance(torch, dict) or torch.get("status") not in OPTIONAL:
        raise ValueError("invalid optional stage")
    required_ok = all(stages[name]["status"] == "passed" for name in REQUIRED)
    consistent = before.get("dirty") is False and after.get("dirty") is False
    expected_overall = "passed" if required_ok and consistent else "failed"
    if (report.get("required_tests_passed") is not required_ok
            or report.get("checkout_consistent") is not consistent
            or report.get("overall") != expected_overall
            or report.get("device_identity_verified") is not False
            or report.get("deployment_approval") is not False):
        raise ValueError("contradictory report claims")
    if not isinstance(report.get("started_at"), str):
        raise ValueError("missing started_at")
    from datetime import datetime
    for key in ("started_at", "completed_at"):
        timestamp = datetime.fromisoformat(report[key].replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            raise ValueError("timezone required")
    return report


def import_report(directory: Path, database: Path) -> tuple[dict, bool, str]:
    report = load_report(directory)
    # Stable ID makes repeated imports idempotent, even when the path changes.
    payload = (directory / "run.json").read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    commit = report["before"]["commit"]
    record = {
        "source": "termux_bridge",
        "run_id": "local-manifest:" + digest,
        "commit": commit,
        "status": "success" if report["overall"] == "passed" else "failure",
        "observed_at": report["completed_at"],
        "environment": "android-termux-unverified",
        "details": {
            "manifest_sha256": digest,
            "stages": {name: item["status"] for name, item in report["stages"].items()},
            "checkout_consistent": report["checkout_consistent"],
            "required_tests_passed": report["required_tests_passed"],
            "commit_on_device_verified": False,
            "device_identity_verified": False,
            "manual_review_required": True,
            "deployment_approval": False,
        },
    }
    database.parent.mkdir(parents=True, exist_ok=True)
    ledger = EvidenceLedger(database)
    ledger.initialize()
    fingerprint, inserted = ledger.append(record)
    return record, inserted, fingerprint


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--run-directory", type=Path)
    parser.add_argument("--root", type=Path, default=Path.home() / "klone-next")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--dashboard", type=Path, required=True)
    parser.add_argument("--baseline", help="baseline SHA; default is candidate (no comparison)")
    parser.add_argument("--timeout", type=int, default=240)
    args = parser.parse_args(argv)
    if args.run:
        if args.output_dir is None or not (1 <= args.timeout <= 3600):
            parser.error("--run requires --output-dir and timeout 1..3600")
        directory = args.output_dir.resolve()
        run_battery(args.root.resolve(), directory, args.timeout)
    else:
        directory = args.run_directory.resolve()
    try:
        record, inserted, fingerprint = import_report(directory, args.database)
        candidate = record["commit"]
        baseline = args.baseline or candidate
        if not SHA.fullmatch(baseline):
            parser.error("--baseline must be a 40-character lowercase SHA")
        ledger = EvidenceLedger(args.database)
        args.dashboard.parent.mkdir(parents=True, exist_ok=True)
        args.dashboard.write_text(render(summarize(ledger, candidate),
                                         compare_commits(ledger, baseline, candidate)),
                                  encoding="utf-8")
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps({"candidate": candidate, "baseline": baseline,
                      "status": record["status"], "inserted": inserted,
                      "fingerprint": fingerprint, "dashboard": str(args.dashboard),
                      "manual_review_required": True}, sort_keys=True))
    return 0 if record["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
