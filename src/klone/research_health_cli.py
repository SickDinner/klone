"""Read-only KLONE research health command for local Termux/CI checks."""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from .research_recovery_inspection import inspect_research_recovery
from .research_audit_consistency import inspect_audit_consistency

# Fixed operator guidance: no raw identifiers, dossier contents or database paths.
# Recommendations are informational only; never trigger automatic repair.
_OPERATOR_GUIDANCE = {
    "stuck_runs": "Inspect the run journal; do not resume automatically.",
    "completed_without_outbox": "Review completed run and missing audit event before manual intervention.",
    "completed_missing_snapshot": "Verify snapshot provenance and version; preserve original records.",
    "outbox_missing_completed": "Check run lifecycle consistency before any delivery attempt.",
    "outbox_version_mismatch": "Compare immutable dossier versions and audit references.",
    "malformed_event_ids": "Inspect event identity format; do not rewrite audit history.",
}


def research_health(*, database_path: Path) -> dict[str, object]:
    recovery = inspect_research_recovery(database_path=database_path)
    integrity = inspect_audit_consistency(database_path=database_path)
    issues = {
        "stuck_runs": len(recovery.started_without_terminal),
        "completed_without_outbox": len(recovery.completed_without_outbox),
        "completed_missing_snapshot": len(integrity.completed_missing_snapshot),
        "outbox_missing_completed": len(integrity.outbox_missing_completed),
        "outbox_version_mismatch": len(integrity.outbox_version_mismatch),
        "malformed_event_ids": len(integrity.malformed_event_ids),
    }
    pending_delivery = len(recovery.pending_audit_delivery)
    status = "attention" if any(issues.values()) else "ok"
    severity = ("critical" if any(issues[key] for key in (
        "completed_without_outbox", "completed_missing_snapshot",
        "outbox_missing_completed", "outbox_version_mismatch",
        "malformed_event_ids")) else
        "warning" if issues["stuck_runs"] else
        "info" if pending_delivery else "none")
    return {
        "status": status,
        "severity": severity,
        "delivery_status": "pending" if pending_delivery else "clear",
        "issue_codes": sorted(key for key, count in issues.items() if count),
        "operator_guidance": [
            {"code": key, "action": _OPERATOR_GUIDANCE[key], "count": issues[key]}
            for key in sorted(issues) if issues[key]
        ],
        "stuck_runs": len(recovery.started_without_terminal),
        "completed_without_outbox": len(recovery.completed_without_outbox),
        "pending_audit_delivery": pending_delivery,
        "completed_missing_snapshot": len(integrity.completed_missing_snapshot),
        "outbox_missing_completed": len(integrity.outbox_missing_completed),
        "outbox_version_mismatch": len(integrity.outbox_version_mismatch),
        "malformed_event_ids": len(integrity.malformed_event_ids),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="KLONE read-only research health")
    parser.add_argument("--database", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = research_health(database_path=args.database)
    except (OSError, ValueError, sqlite3.DatabaseError) as exc:
        print(json.dumps({"status": "error", "reason": type(exc).__name__}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
