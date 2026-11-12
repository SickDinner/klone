"""Read-only test evidence summaries and conservative regression detection."""
from __future__ import annotations

from collections import Counter
from datetime import datetime
from .test_evidence_ledger import EvidenceLedger


def _latest_by_run(records: list[dict]) -> dict[tuple[str, str, str], dict]:
    latest = {}
    for record in records:
        key = (record["source"], record["run_id"], record.get("environment", ""))
        when = datetime.fromisoformat(record["observed_at"].replace("Z", "+00:00"))
        previous = latest.get(key)
        if previous is None or when > previous[0]:
            latest[key] = (when, record)
    return {key: pair[1] for key, pair in latest.items()}


def summarize(ledger: EvidenceLedger, commit: str) -> dict:
    records = ledger.list_for_commit(commit)
    current = _latest_by_run(records)
    by_source = {}
    for source in ("github_actions", "termux_bridge"):
        rows = [r for r in current.values() if r["source"] == source]
        counts = Counter(r["status"] for r in rows)
        by_source[source] = {
            "runs": len(rows),
            "success": counts["success"],
            "failure": counts["failure"],
            "pending": counts["pending"],
            "cancelled": counts["cancelled"],
        }
    return {
        "commit": commit,
        "observations": len(records),
        "sources": by_source,
        "review_state": "manual_review_required" if all(x["runs"] for x in by_source.values())
                        else "pending_evidence",
    }


def compare_commits(ledger: EvidenceLedger, baseline: str, candidate: str) -> dict:
    """Compare like-for-like source/environment runs, without auto-approval."""
    before = _latest_by_run(ledger.list_for_commit(baseline))
    after = _latest_by_run(ledger.list_for_commit(candidate))
    # Runs have different IDs across commits; compare environment-level outcomes.
    def groups(rows):
        grouped = {}
        for row in rows.values():
            key = (row["source"], row.get("environment", ""))
            grouped.setdefault(key, []).append(row["status"])
        return grouped

    old, new = groups(before), groups(after)
    regressions = []
    improvements = []
    for key in sorted(old.keys() & new.keys()):
        previous = old[key]
        current = new[key]
        if previous and all(s == "success" for s in previous) and "failure" in current:
            regressions.append({"source": key[0], "environment": key[1], "reason": "success_to_failure"})
        elif "failure" in previous and current and all(s == "success" for s in current):
            improvements.append({"source": key[0], "environment": key[1], "reason": "failure_to_success"})
    return {
        "baseline": baseline,
        "candidate": candidate,
        "regressions": regressions,
        "improvements": improvements,
        "missing_baseline_environments": [
            {"source": k[0], "environment": k[1]} for k in sorted(new.keys() - old.keys())
        ],
        "missing_candidate_environments": [
            {"source": k[0], "environment": k[1]} for k in sorted(old.keys() - new.keys())
        ],
        "review_state": "manual_review_required",
    }
