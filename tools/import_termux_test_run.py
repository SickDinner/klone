"""Import a locally observed KLONE test run into the offline evidence ledger.

The result remains unauthenticated and does not imply deployment approval.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from klone.test_evidence_ledger import EvidenceLedger

STAGES = ("syntax", "cognition", "full", "local_deploy", "torch_probe")
SUMMARY_RE = re.compile(r"^(syntax|cognition|full|local_deploy|torch_probe): exit=([0-9]+)$")
PYTEST_RE = re.compile(r"(?m)([0-9]+) passed(?:, ([0-9]+) skipped)?")
MAX_LOG_BYTES = 1024 * 1024


def inspect_run(directory: Path) -> dict:
    summary_file = directory / "summary.txt"
    if not summary_file.is_file() or summary_file.stat().st_size > 8192:
        raise ValueError("missing or oversized summary")
    lines = summary_file.read_text(encoding="utf-8").splitlines()
    codes = {}
    for line in lines:
        match = SUMMARY_RE.fullmatch(line.strip())
        if match is None or match.group(1) in codes:
            raise ValueError("invalid or duplicate stage")
        codes[match.group(1)] = int(match.group(2))
    if set(codes) != set(STAGES):
        raise ValueError("missing test stage")
    full_log = directory / "full.log"
    if not full_log.is_file() or full_log.stat().st_size > MAX_LOG_BYTES:
        raise ValueError("missing or oversized full test log")
    full = full_log.read_text(encoding="utf-8")
    matches = list(PYTEST_RE.finditer(full))
    if not matches:
        raise ValueError("pytest passed count missing")
    count = int(matches[-1].group(1))
    skipped = int(matches[-1].group(2) or 0)
    if codes["full"] != 0 or count < 1:
        raise ValueError("full test stage not successful")
    return {"stage_exit_codes": codes, "pytest_passed": count,
            "pytest_skipped": skipped, "all_stages_passed": all(
                code == 0 for code in codes.values()
            )}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-directory", required=True, type=Path)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--database", required=True, type=Path)
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[0-9a-f]{40}", args.commit):
        parser.error("commit must be a full lowercase SHA")
    result = inspect_run(args.run_directory)
    record = {
        "source": "termux_bridge",
        "run_id": "local-log:" + args.run_directory.name,
        "commit": args.commit,
        "status": "success" if result["all_stages_passed"] else "failure",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "environment": "android-termux-unverified",
        "details": {
            **result,
            "import_method": "local_logs_manual_commit",
            "device_identity_verified": False,
            "commit_on_device_verified": False,
            "manual_review_required": True,
            "deployment_approval": False,
        },
    }
    args.database.parent.mkdir(parents=True, exist_ok=True)
    ledger = EvidenceLedger(args.database)
    ledger.initialize()
    fingerprint, inserted = ledger.append(record)
    print(json.dumps({"fingerprint": fingerprint, "inserted": inserted,
                      "status": record["status"], "tests": result["pytest_passed"],
                      "review_required": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
