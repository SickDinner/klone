"""v3.4 fail-closed triage; no process starts, HTTP, sqlite or shell in unit tests."""
from __future__ import annotations

import copy
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
import json
import unittest
from unittest.mock import patch

from klone.mission_control_live_v32 import _digest
from klone.service_guard_v34 import (
    inspect_local_services, main, plan_service_recovery,
)

COMMIT = "a" * 40
PORTS = {"main-api": (8000, "klone_api"),
         "next-api": (8001, "klone_api"),
         "control-status": (8010, "status_json"),
         "mission-control-ui": (8011, "ui_reachability"),
         "chat-ui": (8012, "ui_reachability"),
         "recovery-status": (8020, "status_json")}


def observation(*, main="reported_ok_unattested", dashboard="unavailable",
                rest="unavailable"):
    services = []
    for key in sorted(PORTS):
        port, kind = PORTS[key]
        s = main if key == "main-api" else dashboard if key == "mission-control-ui" else rest
        reason = {"reported_ok_unattested": "self_reported_status_ok",
                  "reachable_unverified": "http_200_is_not_app_health",
                  "unverified": "unexpected_status_schema",
                  "unavailable": "connection_failed"}[s]
        services.append({"service_id": key, "port": port, "kind": kind,
                         "observation": s, "reason": reason, "elapsed_ms": 3,
                         "identity_authenticated": False,
                         "application_version_verified": False})
    counts = {s: sum(row["observation"] == s for row in services) for s in (
        "reported_ok_unattested", "reachable_unverified", "unavailable", "unverified")}
    report = {"schema_version": 1, "kind": "klone-local-live-health-v32-lab",
              "observation_source": "local_ipv4_loopback_http_unattested",
              "probe_timeout_ms": 750,
              "probed_count": 6, "services": services,
              "reported_ok_count": counts["reported_ok_unattested"],
              "reachable_ui_count": counts["reachable_unverified"],
              "unavailable_count": counts["unavailable"],
              "unknown_count": counts["unverified"],
              "all_services_reachable_as_observed": counts["unavailable"] == counts["unverified"] == 0,
              "process_identity_authenticated": False,
              "service_origin_authenticated": False, "tls_protection_present": False,
              "agent_health_measured": False, "service_restart_enabled": False,
              "approval_granted": False, "production_readiness_verified": False}
    report["report_sha256"] = _digest(report, "klone-live-v32-report")
    return report


def signed_again(value):
    value["report_sha256"] = _digest({k:v for k,v in value.items() if k!="report_sha256"},
                                    "klone-live-v32-report")
    return value


class ServiceGuardV34Tests(unittest.TestCase):
    def setUp(self):
        self.s = observation()

    def plan(self, item=None):
        return plan_service_recovery(item if item is not None else self.s,
                                     expected_commit_sha=COMMIT)

    def row(self, result, sid):
        return next(x for x in result["services"] if x["service_id"] == sid)

    def test_exact_six_services(self):
        r = self.plan()
        self.assertEqual(r["service_count"], 6)
        self.assertEqual({x["port"] for x in r["services"]}, {8000,8001,8010,8011,8012,8020})

    def test_main_preservation_even_if_ok(self):
        self.assertEqual(self.row(self.plan(), "main-api")["recommended_action"], "preserve_no_restart")

    def test_no_main_restart_on_failure(self):
        r = self.plan(observation(main="unavailable"))
        self.assertEqual(self.row(r,"main-api")["recommended_action"], "inspect_existing_api_manually")
        self.assertEqual(r["operational_review_status"], "primary_api_requires_inspection")

    def test_main_unverified_never_promoted(self):
        r = self.plan(observation(main="unverified"))
        self.assertFalse(r["primary_api_reported_ok_unattested"])

    def test_dashboard_unavailable_is_not_claimed_free(self):
        r = self.plan()
        self.assertEqual(self.row(r,"mission-control-ui")["recommended_action"],
                         "manual_foreground_start_only_after_bind_check")
        self.assertFalse(r["safe_to_assume_port_unbound"])

    def test_dashboard_available_does_not_duplicate(self):
        r = self.plan(observation(dashboard="reachable_unverified"))
        self.assertTrue(r["dashboard_present_as_observed"])
        self.assertEqual(self.row(r,"mission-control-ui")["recommended_action"],
                         "inspect_existing_dashboard_no_duplicate_start")

    def test_dashboard_unverified_does_not_duplicate(self):
        r = self.plan(observation(dashboard="unverified"))
        self.assertFalse(r["dashboard_present_as_observed"])
        self.assertEqual(self.row(r,"mission-control-ui")["recommended_action"],
                         "inspect_existing_dashboard_no_duplicate_start")

    def test_optional_ports_never_auto_launch(self):
        r=self.plan()
        for sid in ("next-api","control-status","chat-ui","recovery-status"):
            self.assertEqual(self.row(r,sid)["recommended_action"], "do_not_autostart_missing_legacy_service")

    def test_missing_legacy_not_primary_failure(self):
        r=self.plan()
        self.assertEqual(r["missing_optional_service_count"],4)
        self.assertEqual(r["operational_review_status"],"primary_api_self_reports_ok")

    def test_optional_available_not_miscounted(self):
        r=self.plan(observation(rest="reported_ok_unattested"))
        self.assertEqual(r["missing_optional_service_count"],0)

    def test_report_disclaims_permissions(self):
        r=self.plan()
        for k in ("git_checkout_authenticated","process_identity_authenticated",
                  "source_health_authenticated","safe_to_assume_port_unbound",
                  "automatic_restart_enabled","database_access_performed",
                  "tasks_executed","approval_granted","production_readiness_verified"):
            self.assertIs(r[k],False,k)

    def test_rows_never_claim_authority(self):
        for r in self.plan()["services"]:
            self.assertFalse(r["service_identity_authenticated"])
            self.assertFalse(r["launch_enabled_by_report"])

    def test_main_priority_only(self):
        r=self.plan(observation(main="unavailable",rest="unavailable"))
        self.assertTrue(self.row(r,"main-api")["manual_review_needed"])
        for sid in ("next-api","control-status","chat-ui","recovery-status"):
            self.assertFalse(self.row(r,sid)["manual_review_needed"])

    def test_sorted_order(self):
        r=self.plan()
        self.assertEqual([x["port"] for x in r["services"]],sorted(x["port"] for x in r["services"]))

    def test_deterministic(self):
        self.assertEqual(self.plan(),self.plan())

    def test_digest_changes_when_health_changes(self):
        self.assertNotEqual(self.plan()["report_sha256"],
                            self.plan(observation(main="unavailable"))["report_sha256"])

    def test_no_raw_service_fields(self):
        self.assertNotIn("database_path",json.dumps(self.plan()))

    def test_hash_shape(self):
        self.assertEqual(len(self.plan()["report_sha256"]),64)

    def test_bad_expected_commit(self):
        for bad in ("", "b"*39,"B"*40,"z"*40,None,1,True):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                plan_service_recovery(self.s,expected_commit_sha=bad)

    def test_bad_snapshot_shape(self):
        for bad in (None,[],False,"{}"):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                plan_service_recovery(bad,expected_commit_sha=COMMIT)

    def test_partial_snapshot_denied(self):
        r=copy.deepcopy(self.s)
        r["services"]=r["services"][:5]
        r["probed_count"]=5
        r["unavailable_count"]-=1
        with self.assertRaises(ValueError):
            self.plan(signed_again(r))

    def test_added_fake_service_denied(self):
        r=copy.deepcopy(self.s)
        r["services"].append(dict(r["services"][0],service_id="made_up",port=8080))
        r["probed_count"]+=1
        r["unavailable_count"]+=1
        with self.assertRaises(ValueError):
            self.plan(signed_again(r))

    def test_unauthenticated_source_is_not_authenticated(self):
        r=copy.deepcopy(self.s)
        r["process_identity_authenticated"]=True
        with self.assertRaises(ValueError):
            self.plan(signed_again(r))

    def test_count_forgery_denied(self):
        r=copy.deepcopy(self.s)
        r["unavailable_count"]=0
        with self.assertRaises(ValueError):
            self.plan(signed_again(r))

    def test_digest_tamper_denied(self):
        r=copy.deepcopy(self.s)
        r["services"][0]["elapsed_ms"]=999
        with self.assertRaises(ValueError):
            self.plan(r)

    def test_service_id_swap_denied(self):
        r=copy.deepcopy(self.s)
        r["services"][0]["port"]=1
        with self.assertRaises(ValueError):
            self.plan(signed_again(r))

    def test_inspect_passes_allowlist(self):
        calls=[]
        def collect(**kwargs):
            calls.append(kwargs)
            return self.s
        r=inspect_local_services(expected_commit_sha=COMMIT,timeout_ms=400,_collector=collect)
        self.assertEqual(calls,[{"service_ids":tuple(sorted(PORTS)),"timeout_ms":400}])
        self.assertEqual(r["service_count"],6)

    def test_inspect_invalid_sha_denies_before_io(self):
        calls=[]
        def collect(**kwargs):
            calls.append(kwargs)
            return self.s
        with self.assertRaises(ValueError):
            inspect_local_services(expected_commit_sha="a",_collector=collect)
        self.assertFalse(calls)

    def test_inspect_timeout_denies_before_io(self):
        calls=[]
        def collect(**kwargs):
            calls.append(kwargs)
            return self.s
        for bad in (0,99,3001,True,0.5,None):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                inspect_local_services(expected_commit_sha=COMMIT,timeout_ms=bad,_collector=collect)
        self.assertFalse(calls)

    def test_inspect_invalid_collector(self):
        with self.assertRaises(ValueError):
            inspect_local_services(expected_commit_sha=COMMIT,_collector=42)

    def test_cli_no_action(self):
        with redirect_stderr(StringIO()),self.assertRaises(SystemExit):
            main([])

    def test_cli_no_commit(self):
        with redirect_stderr(StringIO()),self.assertRaises(SystemExit):
            main(["--inspect-local"])

    def test_cli_arbitrary_host_denied(self):
        with redirect_stderr(StringIO()),self.assertRaises(SystemExit):
            main(["--inspect-local","--expected-commit",COMMIT,"--host","0.0.0.0"])

    def test_cli_arbitrary_port_denied(self):
        with redirect_stderr(StringIO()),self.assertRaises(SystemExit):
            main(["--inspect-local","--expected-commit",COMMIT,"--port","8000"])

    def test_cli_no_background(self):
        with redirect_stderr(StringIO()),self.assertRaises(SystemExit):
            main(["--serve-dashboard","--daemon"])

    def test_cli_no_autostart_legacy(self):
        with redirect_stderr(StringIO()),self.assertRaises(SystemExit):
            main(["--start-next-api"])

    def test_cli_service_start_explicit_only(self):
        with patch("klone.mission_control_dashboard_v33.serve_dashboard",return_value=0) as launch:
            self.assertEqual(main(["--serve-dashboard"]),0)
        launch.assert_called_once_with()

    def test_cli_propagates_bind_failure(self):
        with patch("klone.mission_control_dashboard_v33.serve_dashboard",return_value=2):
            self.assertEqual(main(["--serve-dashboard"]),2)

    def test_cli_rejects_extra_start_args(self):
        with redirect_stderr(StringIO()),self.assertRaises(SystemExit):
            main(["--serve-dashboard","--expected-commit",COMMIT])

    def test_cli_inspection_json(self):
        with patch("klone.service_guard_v34.inspect_local_services",return_value=self.plan()) as inspect:
            out=StringIO()
            with redirect_stdout(out):
                self.assertEqual(main(["--inspect-local","--expected-commit",COMMIT]),0)
        parsed=json.loads(out.getvalue())
        self.assertEqual(parsed["service_count"],6)
        inspect.assert_called_once_with(expected_commit_sha=COMMIT,timeout_ms=750)

    def test_cli_inspection_failure_denied(self):
        with patch("klone.service_guard_v34.inspect_local_services",side_effect=ValueError("invalid")):
            with redirect_stderr(StringIO()),self.assertRaises(SystemExit):
                main(["--inspect-local","--expected-commit",COMMIT])

    def test_cli_no_scan_flags(self):
        with redirect_stderr(StringIO()),self.assertRaises(SystemExit):
            main(["--inspect-local","--expected-commit",COMMIT,"--range","1-65535"])


if __name__ == "__main__":
    unittest.main()
