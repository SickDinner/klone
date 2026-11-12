"""Read-only local comparison CLI for KLONE test evidence.

Usage: python tools/test_evidence_report.py --database PATH --commit SHA
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from klone.test_evidence_ledger import EvidenceLedger


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args(argv)
    if not args.database.is_file():
        parser.error("evidence database does not exist")
    report = EvidenceLedger(args.database).compare(args.commit)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
