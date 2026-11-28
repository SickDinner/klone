"""Parse an explicitly supplied, bounded pytest summary into a local report.

A report is an operator-supplied observation, not a signed attestation.
No network, repository discovery, test execution or persistent writes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from decimal import Decimal

_FIELDS = {
    "passed": "passed", "failed": "failed", "skipped": "skipped",
    "error": "errors", "errors": "errors",
    "warning": "warnings", "warnings": "warnings",
    "xfailed": "xfailed", "xpassed": "xpassed",
    "subtests passed": "subtests_passed",
    "subtests failed": "subtests_failed",
    "subtests skipped": "subtests_skipped",
}
_KEYS = tuple(dict.fromkeys(_FIELDS.values()))
_ITEM = re.compile(r"([0-9]{1,9}) ([a-z ]+)")
_DURATION = re.compile(
    r"(.+) in ([0-9]{1,9}(?:\.[0-9]{1,6})?)s(?: \([0-9:]+\))?"
)


def parse_summary(summary: str, *, commit: str, exit_code: int) -> dict:
    if not isinstance(summary, str) or not 0 < len(summary) <= 2048:
        raise ValueError("expected one bounded summary line")
    line = summary.strip().strip("=").strip()
    if "\n" in line or "\r" in line:
        raise ValueError("expected one summary line")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("expected a full lowercase Git commit SHA")
    if type(exit_code) is not int or not 0 <= exit_code <= 255:
        raise ValueError("invalid process exit code")
    match = _DURATION.fullmatch(line)
    if not match:
        raise ValueError("unsupported pytest summary format")
    counts = dict.fromkeys(_KEYS, 0)
    seen = set()
    for part in match[1].split(", "):
        item = _ITEM.fullmatch(part)
        if not item or item[2] not in _FIELDS:
            raise ValueError("unknown summary item")
        key = _FIELDS[item[2]]
        if key in seen:
            raise ValueError("duplicate summary item")
        seen.add(key)
        counts[key] = int(item[1])
    if not seen.intersection({"passed", "failed", "skipped", "errors", "xfailed", "xpassed"}):
        raise ValueError("missing primary test outcome")
    failures = counts["failed"] + counts["errors"] + counts["subtests_failed"]
    if exit_code != 0 or failures:
        status = "not_passed"
    elif counts["passed"] == 0 or counts["xpassed"]:
        status = "review_required"
    elif counts["skipped"] or counts["xfailed"] or counts["subtests_skipped"]:
        status = "passed_with_exclusions"
    else:
        status = "passed"
    return {
        "schema": "klone.pytest_observation.v1",
        "evidence": "operator_supplied_summary",
        "independently_verified": False,
        "claimed_commit": commit,
        "process_exit_code": exit_code,
        "status": status,
        "counts": counts,
        "duration_seconds": str(Decimal(match[2])),
        "summary_sha256": hashlib.sha256(line.encode("utf-8")).hexdigest(),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--exit-code", type=int, required=True)
    parser.add_argument("--summary", required=True)
    args = parser.parse_args(argv)
    try:
        report = parse_summary(args.summary, commit=args.commit, exit_code=args.exit_code)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
