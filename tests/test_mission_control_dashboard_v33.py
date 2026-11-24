"""v3.3 viewer: local rendering, strict HTTP boundary, no external I/O."""
from __future__ import annotations

from contextlib import contextmanager
import copy
from http.client import HTTPConnection
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import unittest
from unittest.mock import patch

from klone.mission_control_dashboard_v33 import (
    _PROBES, main, make_handler, render_dashboard, serve_dashboard,
)
from klone.mission_control_live_v32 import _digest

ENDPOINTS = {
    "main-api": (8000, "klone_api"),
    "next-api": (8001, "klone_api"),
    "control-status": (8010, "status_json"),
    "chat-ui": (8012, "ui_reachability"),
    "recovery-status": (8020, "status_json"),
}


def snapshot(*, main_ok=True):
    rows = []
    for key in sorted(ENDPOINTS):
        port, kind = ENDPOINTS[key]
        success = key == "main-api" and main_ok
        rows.append({
            "service_id": key, "port": port, "kind": kind,
            "observation": "reported_ok_unattested" if success else "unavailable",
            "reason": "self_reported_status_ok" if success else "connection_failed",
            "elapsed_ms": 2, "identity_authenticated": False,
            "application_version_verified": False,
        })
    value = {
        "schema_version": 1, "kind": "klone-local-live-health-v32-lab",
        "observation_source": "local_ipv4_loopback_http_unattested",
        "probe_timeout_ms": 750, "probed_count": 5, "services": rows,
        "reported_ok_count": 1 if main_ok else 0,
        "reachable_ui_count": 0,
        "unavailable_count": 4 if main_ok else 5,
        "unknown_count": 0,
        "all_services_reachable_as_observed": False,
        "process_identity_authenticated": False,
        "service_origin_authenticated": False,
        "tls_protection_present": False,
        "agent_health_measured": False,
        "service_restart_enabled": False,
        "approval_granted": False,
        "production_readiness_verified": False,
    }
    value["report_sha256"] = _digest(value, "klone-live-v32-report")
    return value


def rehash(report):
    report["report_sha256"] = _digest(
        {k: v for k, v in report.items() if k != "report_sha256"},
        "klone-live-v32-report")
    return report


@contextmanager
def local_server(collector):
    with HTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler) as server:
        server.RequestHandlerClass = make_handler(port=server.server_port, collector=collector)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            yield server.server_port
        finally:
            server.shutdown()
            worker.join(timeout=2)


def get(port, path="/", headers=None):
    conn = HTTPConnection("127.0.0.1", port, timeout=2)
    try:
        conn.request("GET", path, headers=headers or {})
        response = conn.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        conn.close()


class DashboardV33Tests(unittest.TestCase):
    def setUp(self):
        self.base = snapshot()

    def test_render_has_all_five_services(self):
        page = render_dashboard(self.base).decode()
        for key in ("Main API", "Next API", "Control Status", "Chat UI", "Recovery Status"):
            self.assertIn(key, page)

    def test_render_no_private_api_payload(self):
        page = render_dashboard(self.base).decode()
        self.assertNotIn("database_path", page)
        self.assertNotIn("secret", page)

    def test_render_explicit_unattested(self):
        page = render_dashboard(self.base).decode()
        self.assertIn("ei varmennettu", page)
        self.assertIn("Ei agenttien suoritusta", page)

    def test_render_not_production_ready(self):
        page = render_dashboard(self.base).decode()
        self.assertIn("tuotantohyväksyntää", page)

    def test_render_report_sha(self):
        self.assertIn(self.base["report_sha256"], render_dashboard(self.base).decode())

    def test_render_one_source_of_truth(self):
        self.assertEqual(render_dashboard(self.base), render_dashboard(self.base))

    def test_render_self_port_not_probed(self):
        self.assertNotIn("mission-control-ui", _PROBES)
        self.assertIn("Portti 8011", render_dashboard(self.base).decode())

    def test_render_non_dict_fail(self):
        for v in ([], None, "", 1):
            with self.subTest(v=v), self.assertRaises(ValueError):
                render_dashboard(v)

    def test_render_digest_tamper_rejected(self):
        bad = copy.deepcopy(self.base)
        bad["unavailable_count"] = 0
        with self.assertRaises(ValueError):
            render_dashboard(bad)

    def test_render_missing_endpoint_rejected(self):
        bad = copy.deepcopy(self.base)
        bad["services"] = bad["services"][:4]
        bad["probed_count"] = 4
        bad["unavailable_count"] = 3
        with self.assertRaises(ValueError):
            render_dashboard(rehash(bad))

    def test_render_extra_self_endpoint_rejected(self):
        bad = copy.deepcopy(self.base)
        bad["services"].append({
            "service_id": "mission-control-ui", "port": 8011,
            "kind": "ui_reachability", "observation": "reachable_unverified",
            "reason": "http_200_is_not_app_health", "elapsed_ms": 1,
            "identity_authenticated": False, "application_version_verified": False})
        bad["probed_count"] += 1
        bad["reachable_ui_count"] += 1
        with self.assertRaises(ValueError):
            render_dashboard(rehash(bad))

    def test_render_duplicate_endpoint_rejected(self):
        bad = copy.deepcopy(self.base)
        bad["services"][1] = copy.deepcopy(bad["services"][0])
        with self.assertRaises(ValueError):
            render_dashboard(rehash(bad))

    def test_render_no_promoted_authentication(self):
        bad = copy.deepcopy(self.base)
        bad["process_identity_authenticated"] = True
        with self.assertRaises(ValueError):
            render_dashboard(rehash(bad))

    def test_render_unknown_classification_rejected(self):
        bad = copy.deepcopy(self.base)
        bad["services"][0]["observation"] = "production_verified"
        with self.assertRaises(ValueError):
            render_dashboard(rehash(bad))

    def test_render_correct_full_count(self):
        page = render_dashboard(self.base).decode()
        self.assertIn("4 tavoittamatonta", page)

    def test_render_failure_snapshot_still_html(self):
        page = render_dashboard(snapshot(main_ok=False)).decode()
        self.assertIn("5 tavoittamatonta", page)

    def test_render_does_not_echo_raw_fields(self):
        bad = copy.deepcopy(self.base)
        bad["services"][0]["evil"] = "<script>alert(1)</script>"
        with self.assertRaises(ValueError):
            render_dashboard(rehash(bad))

    def test_invalid_ports(self):
        for port in (0, 800, 65536, True, 123.0):
            with self.subTest(port=port), self.assertRaises(ValueError):
                make_handler(port=port)

    def test_invalid_timeouts(self):
        for t in (0, 99, 3001, True, "500"):
            with self.subTest(t=t), self.assertRaises(ValueError):
                make_handler(timeout_ms=t)

    def test_invalid_collector(self):
        with self.assertRaises(ValueError):
            make_handler(collector=42)

    def test_real_http_renders(self):
        calls = []
        def collect(*, service_ids, timeout_ms):
            calls.append((service_ids, timeout_ms))
            return self.base
        with local_server(collect) as port:
            code, headers, body = get(port)
        self.assertEqual(code, 200)
        self.assertEqual(calls, [(_PROBES, 750)])
        self.assertIn(b"KLONE Mission Control", body)
        self.assertEqual(headers["Cache-Control"], "no-store")

    def test_real_http_denies_host_spoof(self):
        with local_server(lambda **kw: self.fail("unexpected probe")) as port:
            code, _, _ = get(port, headers={"Host": "bad.example"})
        self.assertEqual(code, 403)

    def test_real_http_denies_origin_spoof(self):
        with local_server(lambda **kw: self.fail("unexpected probe")) as port:
            code, _, _ = get(port, headers={"Origin": "https://bad.example"})
        self.assertEqual(code, 403)

    def test_real_http_denies_cross_site(self):
        with local_server(lambda **kw: self.fail("unexpected probe")) as port:
            code, _, _ = get(port, headers={"Sec-Fetch-Site": "cross-site"})
        self.assertEqual(code, 403)

    def test_real_http_denies_query_params(self):
        with local_server(lambda **kw: self.fail("unexpected probe")) as port:
            code, _, _ = get(port, path="/?url=http://bad.example")
        self.assertEqual(code, 404)

    def test_real_http_503_on_probe_error(self):
        def broken(**kwargs):
            raise RuntimeError("PRIVATE_DB_PATH=secret")
        with local_server(broken) as port:
            code, _, body = get(port)
        self.assertEqual(code, 503)
        self.assertNotIn(b"PRIVATE_DB_PATH", body)

    def test_real_http_no_cookies(self):
        with local_server(lambda **kw: self.base) as port:
            _, headers, _ = get(port)
        self.assertNotIn("Set-Cookie", headers)

    def test_real_http_security_headers(self):
        with local_server(lambda **kw: self.base) as port:
            _, headers, _ = get(port)
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])

    def test_no_default_launch_without_opt_in(self):
        with self.assertRaises(SystemExit):
            main([])

    def test_cli_opt_in_uses_foreground(self):
        with patch("klone.mission_control_dashboard_v33.serve_dashboard", return_value=0) as mock:
            self.assertEqual(main(["--serve-local"]), 0)
        mock.assert_called_once_with()

    def test_cli_rejects_arbitrary_port(self):
        with self.assertRaises(SystemExit):
            main(["--serve-local", "--port", "8123"])

    def test_only_fixed_endpoints(self):
        self.assertEqual(set(_PROBES), set(ENDPOINTS))

    def test_render_is_bytes(self):
        self.assertIsInstance(render_dashboard(self.base), bytes)

    def test_server_error_does_not_stop_api(self):
        with patch("klone.mission_control_dashboard_v33.HTTPServer", side_effect=OSError("port busy")):
            self.assertEqual(serve_dashboard(), 2)


if __name__ == "__main__":
    unittest.main()
