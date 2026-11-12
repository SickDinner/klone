"""Import explicitly reviewed KLONE evidence JSON from local disk.

This tool does not download GitHub artifacts or infer source authenticity.
Only import files from trusted, independently verified origins.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from klone.test_evidence_ledger import EvidenceLedger, validate

MAX_BYTES = 10240


def load_record(path: Path) -> dict:
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("evidence file too large")
    with path.open("r", encoding="utf-8") as handle:
        record = json.load(handle)
    return validate(record)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument("--expected-source", choices=["github_actions", "termux_bridge"], required=True)
    parser.add_argument("--expected-commit", required=True)
    args = parser.parse_args(argv)
    record = load_record(args.file)
    if record["source"] != args.expected_source or record["commit"] != args.expected_commit:
        parser.error("evidence source or commit does not match explicit expectation")
    args.database.parent.mkdir(parents=True, exist_ok=True)
    ledger = EvidenceLedger(args.database)
    ledger.initialize()
    fingerprint, inserted = ledger.append(record)
    print(json.dumps({"fingerprint": fingerprint, "inserted": inserted, "source": record["source"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
