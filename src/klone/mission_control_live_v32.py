"""KLONE v3.2: bounded localhost-only Mission Control health observations (LAB).

Only fixed loopback HTTP GETs are allowed. Endpoint contents are untrusted and
never copied into output; a claimed health value is NOT authentication. There
is no web/API route, persistence, authorization, agent execution, or restart.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
import argparse
import http.client
import hmac
import json
import re
import time

_MAX_BODY = 8192
_SHA40 = re.compile(r"[0-9a-f]{40}\Z")
_SHA64 = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class _Endpoint:
    service_id: str
    port: int
    path: str
    category: str


# The ONLY permitted destinations. Do not accept URLs, hostnames or ports from
# untrusted CLI arguments. The UI checks deliberately prove reachability only.
_ENDPOINTS = (
    _Endpoint("main-api", 8000, "/api/health", "klone_api"),
    _Endpoint("next-api", 8001, "/api/health", "klone_api"),
    _Endpoint("control-status", 8010, "/status.json", "status_json"),
    _Endpoint("mission-control-ui", 8011, "/", "ui_reachability"),
    _Endpoint("chat-ui", 8012, "/", "ui_reachability"),
    _Endpoint("recovery-status", 8020, "/status.json", "status_json"),
)
_BY_ID = {e.service_id: e for e in _ENDPOINTS}


def _pairs_unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate_json_key")
        value[key] = item
    return value


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("ascii")


def _digest(value: object, domain: str) -> str:
    return sha256(domain.encode("ascii") + b"\0" + _canonical(value)).hexdigest()


def supported_local_services() -> tuple[str, ...]:
    """Auditable, fixed local allowlist. Does not scan the local network."""
    return tuple(e.service_id for e in _ENDPOINTS)


def _probe(endpoint: _Endpoint, timeout: float, connection_factory) -> dict:
    start = time.monotonic_ns()
    connection = None
    result, reason = "unavailable", "connection_failed"
    try:
        # Numerical IPv4 loopback literal; no DNS, proxies, redirects or URL
        # parsing. Even a 200 response makes no identity/security claim.
        connection = connection_factory("127.0.0.1", endpoint.port, timeout=timeout)
        connection.request("GET", endpoint.path,
                           headers={"Accept": "application/json", "Connection": "close"})
        response = connection.getresponse()
        code = response.status
        if code != 200:
            result, reason = "unavailable", "unexpected_http_status"
        elif endpoint.category == "ui_reachability":
            # Do not read/copy arbitrary HTML, cookies or application contents.
            result, reason = "reachable_unverified", "http_200_is_not_app_health"
        else:
            ctype = response.getheader("Content-Type", "")
            # A possibly hostile local endpoint may return JSON-shaped HTML.
            # Refuse it instead of guessing the contents.
            if ctype.split(";", 1)[0].strip().lower() != "application/json":
                result, reason = "unverified", "invalid_content_type"
            else:
                body = response.read(_MAX_BODY + 1)
                if len(body) > _MAX_BODY:
                    result, reason = "unverified", "response_too_large"
                else:
                    try:
                        doc = json.loads(body.decode("utf-8"), object_pairs_hook=_pairs_unique,
                                         parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
                    except (ValueError, UnicodeError, RecursionError, TypeError):
                        result, reason = "unverified", "invalid_json"
                    else:
                        if (type(doc) is dict and type(doc.get("status")) is str
                                and doc["status"] == "ok"
                                and (endpoint.category != "klone_api" or doc.get("app") == "Klone")):
                            result, reason = "reported_ok_unattested", "self_reported_status_ok"
                        else:
                            result, reason = "unverified", "unexpected_status_schema"
    except (OSError, TimeoutError, http.client.HTTPException, ValueError, TypeError, AttributeError):
        # No exception messages or URLs: errors can contain server-supplied data.
        result, reason = "unavailable", "connection_failed"
    finally:
        if connection is not None:
            try:
                connection.close()
            except OSError:
                pass
    duration_ms = max(0, (time.monotonic_ns() - start) // 1_000_000)
    return {"service_id": endpoint.service_id, "port": endpoint.port,
            "kind": endpoint.category, "observation": result,
            "reason": reason, "elapsed_ms": min(duration_ms, 60000),
            "identity_authenticated": False, "application_version_verified": False}


def collect_local_service_observations(*, service_ids: Sequence[str] | None = None,
                                       timeout_ms: int = 750,
                                       _connection_factory=None) -> dict:
    """Opt-in bounded local TCP probes, never arbitrary ports or addresses.

    `_connection_factory` is solely a test seam; injecting an alternate
    transport does not create attestation. No hidden background monitoring.
    """
    if type(timeout_ms) is not int or not 100 <= timeout_ms <= 3000:
        raise ValueError("invalid_probe_timeout")
    ids = supported_local_services() if service_ids is None else service_ids
    if (not isinstance(ids, Sequence) or isinstance(ids, (str, bytes))
            or not 1 <= len(ids) <= len(_ENDPOINTS)):
        raise ValueError("invalid_service_selection")
    if any(type(i) is not str or i not in _BY_ID for i in ids):
        raise ValueError("unknown_local_service")
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate_local_service")
    if _connection_factory is not None and not callable(_connection_factory):
        raise ValueError("invalid_probe_transport")
    transport = http.client.HTTPConnection if _connection_factory is None else _connection_factory
    rows = [_probe(_BY_ID[i], timeout_ms / 1000, transport) for i in sorted(ids)]
    report = {"schema_version": 1, "kind": "klone-local-live-health-v32-lab",
              "observation_source": "local_ipv4_loopback_http_unattested",
              "probe_timeout_ms": timeout_ms, "probed_count": len(rows),
              "services": rows,
              "reported_ok_count": sum(x["observation"] == "reported_ok_unattested" for x in rows),
              "reachable_ui_count": sum(x["observation"] == "reachable_unverified" for x in rows),
              "unavailable_count": sum(x["observation"] == "unavailable" for x in rows),
              "unknown_count": sum(x["observation"] == "unverified" for x in rows),
              "all_services_reachable_as_observed": all(x["observation"] in (
                  "reported_ok_unattested", "reachable_unverified") for x in rows),
              "process_identity_authenticated": False,
              "service_origin_authenticated": False,
              "tls_protection_present": False,
              "agent_health_measured": False, "service_restart_enabled": False,
              "approval_granted": False, "production_readiness_verified": False}
    report["report_sha256"] = _digest(report, "klone-live-v32-report")
    return report


def _validate_live_report(report: object) -> None:
    if type(report) is not dict or len(_canonical(report)) > 32768:
        raise ValueError("invalid_live_report")
    if set(report) != {"schema_version", "kind", "observation_source",
                       "probe_timeout_ms", "probed_count", "services", "reported_ok_count",
                       "reachable_ui_count", "unavailable_count", "unknown_count",
                       "all_services_reachable_as_observed", "process_identity_authenticated",
                       "service_origin_authenticated", "tls_protection_present", "agent_health_measured",
                       "service_restart_enabled", "approval_granted", "production_readiness_verified",
                       "report_sha256"}:
        raise ValueError("invalid_live_report_shape")
    # A plain digest cannot attest who produced this snapshot.
    if type(report["report_sha256"]) is not str or not _SHA64.fullmatch(report["report_sha256"]):
        raise ValueError("invalid_live_report_digest")
    document = {k: v for k, v in report.items() if k != "report_sha256"}
    if not hmac.compare_digest(report["report_sha256"], _digest(document, "klone-live-v32-report")):
        raise ValueError("tampered_live_report")
    if (type(report["schema_version"]) is not int or report["schema_version"] != 1
            or report["kind"] != "klone-local-live-health-v32-lab"
            or report["observation_source"] != "local_ipv4_loopback_http_unattested"
            or type(report["probe_timeout_ms"]) is not int
            or not 100 <= report["probe_timeout_ms"] <= 3000):
        raise ValueError("invalid_live_report_identity")
    if any(report[k] is not False for k in (
            "process_identity_authenticated", "service_origin_authenticated",
            "tls_protection_present", "agent_health_measured", "service_restart_enabled",
            "approval_granted", "production_readiness_verified")):
        raise ValueError("invalid_live_authority_claim")
    if (type(report["services"]) is not list or not 1 <= len(report["services"]) <= len(_ENDPOINTS)
            or type(report["probed_count"]) is not int
            or report["probed_count"] != len(report["services"])):
        raise ValueError("invalid_live_service_rows")
    # Validate reported rows and recompute counts to prevent a forged summary.
    seen = set()
    count = {"reported_ok_unattested": 0, "reachable_unverified": 0,
             "unavailable": 0, "unverified": 0}
    for row in report["services"]:
        if type(row) is not dict or set(row) != {
                "service_id", "port", "kind", "observation", "reason", "elapsed_ms",
                "identity_authenticated", "application_version_verified"}:
            raise ValueError("invalid_live_service_row")
        endpoint = _BY_ID.get(row["service_id"]) if type(row["service_id"]) is str else None
        if endpoint is None or row["service_id"] in seen:
            raise ValueError("invalid_live_service_identity")
        seen.add(row["service_id"])
        if row["port"] != endpoint.port or row["kind"] != endpoint.category:
            raise ValueError("invalid_live_service_scope")
        if (type(row["observation"]) is not str or row["observation"] not in count
                or type(row["reason"]) is not str or not re.fullmatch(r"[a-z0-9_]{1,64}", row["reason"])
                or type(row["elapsed_ms"]) is not int
                or not 0 <= row["elapsed_ms"] <= 60000 or
                row["identity_authenticated"] is not False or
                row["application_version_verified"] is not False):
            raise ValueError("invalid_live_service_measurement")
        count[row["observation"]] += 1
    if (any(type(report[key]) is not int for key in (
            "reported_ok_count", "reachable_ui_count", "unavailable_count", "unknown_count"))
            or type(report["all_services_reachable_as_observed"]) is not bool
            or report["reported_ok_count"] != count["reported_ok_unattested"]
            or report["reachable_ui_count"] != count["reachable_unverified"]
            or report["unavailable_count"] != count["unavailable"]
            or report["unknown_count"] != count["unverified"]
            or report["all_services_reachable_as_observed"] is not (count["unavailable"] == 0 and count["unverified"] == 0)):
        raise ValueError("inconsistent_live_summary")


def compose_live_mission_control_review(base_review: Mapping, live_report: Mapping) -> dict:
    """Conservative overlay over existing v3.1, no promotion from health HTTP."""
    if type(base_review) is not dict or len(_canonical(base_review)) > 65536:
        raise ValueError("invalid_v31_review")
    if (base_review.get("kind") != "klone-mission-control-observatory-v31-lab"
            or type(base_review.get("expected_commit_sha")) is not str
            or not _SHA40.fullmatch(base_review["expected_commit_sha"])
            or type(base_review.get("report_sha256")) is not str
            or not _SHA64.fullmatch(base_review["report_sha256"])
            or any(base_review.get(flag) is not False for flag in (
                "permission_granted", "tasks_dispatched", "deployment_approval",
                "production_readiness_verified", "report_sources_authenticated"))):
        raise ValueError("invalid_v31_review_authority")
    if base_review.get("review_status") not in ("manual_review_required", "blocked_for_review"):
        raise ValueError("invalid_v31_review_status")
    from .acceptance_matrix import DOMAINS
    allowed_reasons = {"domain:" + name for name in DOMAINS} | {
        "runtime_identity_unverified", "external_provenance_unverified",
        "independent_audit_anchor_unverified", "production_approval_absent",
        "memory_continuity_conflict", "regression_matrix_incomplete",
        "regression_commit_mismatch", "regression_reported_failure",
        "regression_total_count_disagreement", "regression_report_digest_missing",
        "council_proof_not_supplied", "council_proof_requires_review",
        "test_provenance_unverified",
    }
    base_without_hash = {k: v for k, v in base_review.items() if k != "report_sha256"}
    expected_base_hash = sha256(_canonical({"domain": "klone-v31-mission-control",
                                             "report": base_without_hash})).hexdigest()
    if not hmac.compare_digest(base_review["report_sha256"], expected_base_hash):
        raise ValueError("tampered_v31_review")
    base_reasons = base_review.get("review_reasons")
    if (type(base_reasons) is not list or len(base_reasons) > 64
            or any(type(x) is not str or x not in allowed_reasons for x in base_reasons)):
        raise ValueError("invalid_v31_review_reasons")
    if type(live_report) is not dict:
        raise ValueError("invalid_live_report")
    _validate_live_report(live_report)
    hard_hold = base_review["review_status"] == "blocked_for_review"
    if live_report["unavailable_count"] or live_report["unknown_count"]:
        hard_hold = True
    reasons = sorted(set(base_review.get("review_reasons", [])) | (
        {"local_service_unavailable_or_unverified"} if live_report["unavailable_count"] or
        live_report["unknown_count"] else set()))
    result = {"schema_version": 1, "kind": "klone-mission-control-live-review-v32-lab",
              "expected_commit_sha": base_review["expected_commit_sha"],
              "base_review_sha256_claim": base_review["report_sha256"],
              "local_observation_sha256": live_report["report_sha256"],
              "services_reported_ok": live_report["reported_ok_count"],
              "services_ui_reachable": live_report["reachable_ui_count"],
              "services_unavailable": live_report["unavailable_count"],
              "services_unknown": live_report["unknown_count"],
              "review_status": "blocked_for_review" if hard_hold else "manual_review_required",
              "review_reasons": reasons,
              "base_review_recomputed": False,
              "service_health_as_claimed_only": True,
              "report_sources_authenticated": False,
              "service_identity_authenticated": False,
              "memory_snapshot_authenticated": False,
              "permission_granted": False, "tasks_dispatched": False,
              "deployment_approval": False, "production_readiness_verified": False,
              "human_review_required": True}
    result["report_sha256"] = _digest(result, "klone-v32-live-overlay")
    return result



def build_live_mission_control_review(
    *, expected_commit_sha: str, domain_states: Mapping[str, str],
    memory_before: Sequence, memory_after: Sequence,
    regression_claims: Sequence = (), proof_inputs=None,
    service_ids: Sequence[str] | None = None, timeout_ms: int = 750,
    _connection_factory=None,
) -> dict:
    """Recompute actual v3.1 logic *before* any opt-in local service probe.

    The supplied memories and regression records still have unauthenticated
    origins. Live service reports never create security grants or readiness.
    """
    from .mission_control_observatory_v31 import build_mission_control_review

    base = build_mission_control_review(
        expected_commit_sha=expected_commit_sha, domain_states=domain_states,
        memory_before=memory_before, memory_after=memory_after,
        regression_claims=regression_claims, proof_inputs=proof_inputs)
    live = collect_local_service_observations(
        service_ids=service_ids, timeout_ms=timeout_ms,
        _connection_factory=_connection_factory)
    result = compose_live_mission_control_review(base, live)
    result["base_review_recomputed"] = True
    result["report_sha256"] = _digest(
        {k: v for k, v in result.items() if k != "report_sha256"},
        "klone-v32-live-overlay")
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only local KLONE port checks (LAB)")
    parser.add_argument("--probe-local", action="store_true",
                        help="explicitly enable fixed 127.0.0.1 loopback HTTP requests")
    parser.add_argument("--service", choices=supported_local_services(), action="append")
    parser.add_argument("--timeout-ms", type=int, default=750)
    args = parser.parse_args(argv)
    if not args.probe_local:
        parser.error("--probe-local is mandatory; no implicit network probes")
    try:
        report = collect_local_service_observations(service_ids=args.service,
                                                   timeout_ms=args.timeout_ms)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(report, sort_keys=True, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
