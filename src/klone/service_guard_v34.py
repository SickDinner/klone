"""KLONE v3.4 LAB: explicit, read-only service triage and safe dashboard entrypoint.

The 8000 application is managed externally. This module NEVER kills, restarts,
installs, migrates, writes a DB, or starts a server except by an explicit
foreground --serve-dashboard command (existing v3.3 launcher, fixed 8011).
Local HTTP health signals do not prove service identity or process ownership.
"""
from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from hashlib import sha256
import json
import re

from .mission_control_live_v32 import (
    _validate_live_report, collect_local_service_observations,
)

_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_MANAGED = ("main-api", "mission-control-ui")
_OPTIONAL = ("next-api", "control-status", "chat-ui", "recovery-status")
_EXPECTED = frozenset(_MANAGED + _OPTIONAL)
_SERVICE_PORTS = {
    "main-api": 8000,
    "next-api": 8001,
    "control-status": 8010,
    "mission-control-ui": 8011,
    "chat-ui": 8012,
    "recovery-status": 8020,
}


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      allow_nan=False, ensure_ascii=True).encode("ascii")


def plan_service_recovery(report: Mapping, *, expected_commit_sha: str) -> dict:
    """Triage a validated v3.2 observation snapshot without acting on it.

    API 8000 is an existing externally managed service; v3.4 can only suggest
    manually starting the standalone v3.3 dashboard on 8011. No other service
    has a known safe v3.4 launch contract. HTTP failures do NOT prove free ports.
    """
    if type(expected_commit_sha) is not str or not _COMMIT.fullmatch(expected_commit_sha):
        raise ValueError("invalid_expected_commit")
    if type(report) is not dict:
        raise ValueError("invalid_service_report")
    _validate_live_report(report)
    rows = report["services"]
    if {r["service_id"] for r in rows} != _EXPECTED or len(rows) != len(_EXPECTED):
        raise ValueError("incomplete_service_inventory")
    results = []
    main = next(r for r in rows if r["service_id"] == "main-api")
    # A main API reporting OK is still unauthenticated, but it is important
    # operational evidence that must not be interpreted as safe-to-restart.
    main_operational = main["observation"] == "reported_ok_unattested"
    for row in sorted(rows, key=lambda x: (x["port"], x["service_id"])):
        sid, observed = row["service_id"], row["observation"]
        if sid == "main-api":
            category = "external_primary_api"
            action = "preserve_no_restart" if main_operational else "inspect_existing_api_manually"
            needed = not main_operational
        elif sid == "mission-control-ui":
            category = "manual_dashboard_frontend"
            action = ("inspect_existing_dashboard_no_duplicate_start"
                      if observed != "unavailable" else
                      "manual_foreground_start_only_after_bind_check")
            needed = observed == "unavailable"
        else:
            category = "optional_legacy_endpoint"
            action = "do_not_autostart_missing_legacy_service"
            needed = False
        results.append({"service_id": sid, "port": _SERVICE_PORTS[sid],
                        "category": category, "observation": observed,
                        "recommended_action": action, "manual_review_needed": needed,
                        "service_identity_authenticated": False,
                        "launch_enabled_by_report": False})
    output = {
        "schema_version": 1,
        "kind": "klone-service-guard-v34-lab",
        "expected_commit_sha_claim": expected_commit_sha,
        "live_observation_sha256": report["report_sha256"],
        "service_count": len(results), "services": results,
        "primary_api_reported_ok_unattested": main_operational,
        "dashboard_present_as_observed": next(r for r in rows if r["service_id"] == "mission-control-ui")["observation"] == "reachable_unverified",
        "missing_optional_service_count": sum(r["category"] == "optional_legacy_endpoint" and r["observation"] == "unavailable" for r in results),
        "operational_review_status": "primary_api_self_reports_ok" if main_operational else "primary_api_requires_inspection",
        "git_checkout_authenticated": False,
        "process_identity_authenticated": False,
        "source_health_authenticated": False,
        "safe_to_assume_port_unbound": False,
        "automatic_restart_enabled": False,
        "database_access_performed": False,
        "tasks_executed": False,
        "approval_granted": False,
        "production_readiness_verified": False,
    }
    if len(_canonical(output)) > 32768:
        raise ValueError("service_report_too_large")
    output["report_sha256"] = sha256(b"klone-v34-service-triage\0"+_canonical(output)).hexdigest()
    return output


def inspect_local_services(*, expected_commit_sha: str, timeout_ms: int = 750,
                           _collector: Callable | None = None) -> dict:
    """Explicit opt-in local checks; no background polling or role grants."""
    if type(expected_commit_sha) is not str or not _COMMIT.fullmatch(expected_commit_sha):
        raise ValueError("invalid_expected_commit")
    if type(timeout_ms) is not int or not 100 <= timeout_ms <= 3000:
        raise ValueError("invalid_inspection_timeout")
    if _collector is not None and not callable(_collector):
        raise ValueError("invalid_inspection_collector")
    collect = collect_local_service_observations if _collector is None else _collector
    report = collect(service_ids=tuple(sorted(_EXPECTED)), timeout_ms=timeout_ms)
    return plan_service_recovery(report, expected_commit_sha=expected_commit_sha)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="KLONE v3.4 local service guard (LAB)")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--inspect-local", action="store_true",
                        help="read-only check of 6 fixed localhost services")
    action.add_argument("--serve-dashboard", action="store_true",
                        help="manual foreground v3.3 viewer on 127.0.0.1:8011; never restart")
    parser.add_argument("--expected-commit", help="explicit 40-hex commit claim for the report")
    parser.add_argument("--timeout-ms", type=int, default=750)
    args = parser.parse_args(argv)
    if args.serve_dashboard:
        if args.expected_commit is not None or args.timeout_ms != 750:
            parser.error("dashboard_mode_has_no_extra_options")
        from .mission_control_dashboard_v33 import serve_dashboard
        # Original server binds 127.0.0.1:8011; bind failure is an error.
        # It never inherits user-supplied ports or database paths.
        return serve_dashboard()
    if args.expected_commit is None:
        parser.error("--expected-commit vaaditaan, jotta raportilla on vertailucommit")
    try:
        result = inspect_local_services(expected_commit_sha=args.expected_commit,
                                        timeout_ms=args.timeout_ms)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(result, sort_keys=True, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
