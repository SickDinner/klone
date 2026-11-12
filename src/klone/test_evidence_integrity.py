"""Read-only KLONE evidence integrity audit and conservative decision gate.

Hashes detect local corruption when compared to an independently stored digest.
They do not authenticate a device, GitHub or the evidence producer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from klone.test_evidence_ledger import canonical, validate
from klone.test_evidence_dashboard import compare_commits, summarize
from klone.test_evidence_ledger import EvidenceLedger

SHA = re.compile(r"^[0-9a-f]{40}$")


def audit(database: Path) -> dict:
    if not database.is_file():
        raise ValueError("evidence database missing")
    connection = sqlite3.connect(f"file:{database.resolve()}?mode=ro", uri=True)
    try:
        rows = connection.execute(
            "SELECT fingerprint, source, run_id, commit_sha, status, observed_at, payload_json "
            "FROM test_evidence ORDER BY fingerprint"
        ).fetchall()
    finally:
        connection.close()
    issues = []
    digest = bytes(32)
    for fingerprint, source, run_id, commit, status, observed, payload in rows:
        try:
            parsed = json.loads(payload)
            normalized = canonical(validate(parsed))
            expected = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
            if expected != fingerprint or normalized != payload:
                issues.append({"fingerprint": fingerprint, "reason": "payload_fingerprint_mismatch"})
            if (parsed["source"], parsed["run_id"], parsed["commit"],
                    parsed["status"], parsed["observed_at"]) != (
                    source, run_id, commit, status, observed):
                issues.append({"fingerprint": fingerprint, "reason": "indexed_columns_mismatch"})
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            issues.append({"fingerprint": fingerprint, "reason": "invalid_payload"})
        digest = hashlib.sha256(digest + fingerprint.encode("utf-8") +
                                payload.encode("utf-8")).digest()
    return {"records": len(rows), "valid": not issues, "issues": issues,
            "snapshot_sha256": digest.hex(), "external_anchor_verified": False}


def assess(database: Path, baseline: str, candidate: str) -> dict:
    if not SHA.fullmatch(baseline) or not SHA.fullmatch(candidate):
        raise ValueError("full lowercase SHA required")
    integrity = audit(database)
    if not integrity["valid"]:
        return {"decision": "blocked", "reasons": ["evidence_integrity_failed"],
                "integrity": integrity, "deployment_approval": False}
    ledger = EvidenceLedger(database)
    summary = summarize(ledger, candidate)
    comparison = compare_commits(ledger, baseline, candidate)
    reasons = []
    if not any(v["runs"] for v in summary["sources"].values()):
        reasons.append("no_candidate_evidence")
    if comparison["regressions"]:
        reasons.append("detected_regression")
    if comparison["missing_candidate_environments"]:
        reasons.append("missing_candidate_environment")
    if summary["sources"]["github_actions"]["runs"] == 0:
        reasons.append("missing_ci_evidence")
    if summary["sources"]["termux_bridge"]["runs"] == 0:
        reasons.append("missing_termux_evidence")
    if any(v["failure"] or v["pending"] or v["cancelled"] for v in summary["sources"].values()):
        reasons.append("non_successful_candidate_run")
    # An intact local DB is not an independently attested, trusted deployment approval.
    return {"decision": "blocked" if reasons else "manual_review_required",
            "reasons": reasons, "integrity": integrity,
            "comparison": comparison, "summary": summary,
            "deployment_approval": False, "device_identity_verified": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        report = assess(args.database, args.baseline, args.candidate)
    except (ValueError, sqlite3.Error) as exc:
        parser.error(str(exc))
    result = json.dumps(report, sort_keys=True, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result + "\n", encoding="utf-8")
    print(result)
    return 2 if report["decision"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
