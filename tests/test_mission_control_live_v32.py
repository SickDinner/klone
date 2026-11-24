"""No real network: fixed-port transport mock + v3.1 local integration."""
import copy
import io
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import unittest
from unittest.mock import patch
from contextlib import redirect_stderr, redirect_stdout

from klone.mission_control_live_v32 import (
    _validate_live_report, collect_local_service_observations,
    compose_live_mission_control_review, build_live_mission_control_review,
    main, supported_local_services)
from klone.acceptance_matrix import DOMAINS
from klone.memory_continuity_v30 import PublicMemoryEvent
from klone.mission_control_observatory_v31 import build_mission_control_review

COMMIT = "f" * 40
DATE = "2026-11-24T08:00:00+00:00"


class Response:
    def __init__(self, status=200, payload=b'{"status":"ok","app":"Klone"}', ctype="application/json"):
        self.status, self.payload, self.ctype = status, payload, ctype
        self.read_calls = 0

    def getheader(self, name, default=""):
        return self.ctype if name == "Content-Type" else default

    def read(self, length):
        self.read_calls += 1
        return self.payload[:length]


class Factory:
    def __init__(self, response=None, exception=None):
        self.response, self.exception = response or Response(), exception
        self.opened = []

    def __call__(self, host, port, timeout):
        conn = Connection(self.response, self.exception)
        self.opened.append((host, port, timeout, conn))
        return conn


class Connection:
    def __init__(self, response, exception):
        self.response, self.exception = response, exception
        self.closed = False
        self.requests = []

    def request(self, method, path, headers):
        self.requests.append((method, path, headers))
        if self.exception:
            raise self.exception

    def getresponse(self):
        return self.response

    def close(self):
        self.closed = True


def sample_base():
    event = PublicMemoryEvent(event_id=1, occurred_at=DATE, recorded_at=DATE)
    return build_mission_control_review(
        expected_commit_sha=COMMIT,
        domain_states=dict.fromkeys(DOMAINS, "unverified"),
        memory_before=[event], memory_after=[event])


class ProbeTests(unittest.TestCase):
    def sample(self, service_ids=("main-api",), response=None, exception=None):
        factory = Factory(response, exception)
        return collect_local_service_observations(
            service_ids=service_ids, timeout_ms=700, _connection_factory=factory), factory

    def test_allowlist_only_and_complete(self):
        self.assertEqual(len(supported_local_services()), 6)
        self.assertEqual(set(supported_local_services()), {
            "main-api", "next-api", "control-status", "mission-control-ui",
            "chat-ui", "recovery-status"})

    def test_api_200_ok_claim_only(self):
        report, factory = self.sample()
        self.assertEqual(report["reported_ok_count"], 1)
        self.assertFalse(report["service_origin_authenticated"])
        self.assertFalse(report["production_readiness_verified"])
        self.assertEqual(factory.opened[0][0], "127.0.0.1")
        self.assertEqual(factory.opened[0][1], 8000)
        self.assertEqual(factory.opened[0][3].requests[0][0], "GET")
        self.assertEqual(factory.opened[0][3].requests[0][1], "/api/health")
        self.assertTrue(factory.opened[0][3].closed)

    def test_status_endpoint_no_app_field_required(self):
        result, _ = self.sample(("recovery-status",), Response(payload=b'{"status":"ok"}'))
        self.assertEqual(result["reported_ok_count"], 1)

    def test_api_wrong_app_fails_unverified(self):
        result, _ = self.sample(response=Response(payload=b'{"status":"ok","app":"Other"}'))
        self.assertEqual(result["services"][0]["observation"], "unverified")

    def test_ui_http200_only_reachable(self):
        response = Response(payload=b'<html>private stuff</html>', ctype="text/html")
        result, factory = self.sample(("mission-control-ui",), response)
        self.assertEqual(result["reachable_ui_count"], 1)
        self.assertFalse(result["service_origin_authenticated"])
        self.assertEqual(response.read_calls, 0)
        self.assertNotIn("private stuff", json.dumps(result))
        self.assertEqual(factory.opened[0][3].requests[0][1], "/")

    def test_redirect_not_followed(self):
        result, factory = self.sample(response=Response(status=302))
        self.assertEqual(result["services"][0]["reason"], "unexpected_http_status")
        self.assertEqual(len(factory.opened), 1)
        self.assertTrue(factory.opened[0][3].closed)

    def test_auth_error_not_healthy(self):
        result, _ = self.sample(response=Response(status=401))
        self.assertEqual(result["unavailable_count"], 1)

    def test_server_error_not_healthy(self):
        result, _ = self.sample(response=Response(status=500))
        self.assertFalse(result["all_services_reachable_as_observed"])

    def test_timeout_fail_closed_and_connection_closed(self):
        result, factory = self.sample(exception=TimeoutError("not for stdout"))
        self.assertEqual(result["unavailable_count"], 1)
        self.assertNotIn("not for stdout", json.dumps(result))
        self.assertTrue(factory.opened[0][3].closed)

    def test_refused_fail_closed(self):
        result, _ = self.sample(exception=ConnectionRefusedError("refused"))
        self.assertEqual(result["services"][0]["observation"], "unavailable")

    def test_status_json_case_strict(self):
        result, _ = self.sample(response=Response(payload=b'{"status":"OK","app":"Klone"}'))
        self.assertEqual(result["unknown_count"], 1)

    def test_status_null_rejected(self):
        result, _ = self.sample(response=Response(payload=b'{"status":null,"app":"Klone"}'))
        self.assertEqual(result["unknown_count"], 1)

    def test_duplicate_json_keys_rejected(self):
        result, _ = self.sample(response=Response(payload=b'{"status":"ok","status":"ok","app":"Klone"}'))
        self.assertEqual(result["services"][0]["reason"], "invalid_json")

    def test_nan_json_rejected(self):
        result, _ = self.sample(response=Response(payload=b'{"status":"ok","app":"Klone","f":NaN}'))
        self.assertEqual(result["unknown_count"], 1)

    def test_json_array_rejected(self):
        result, _ = self.sample(response=Response(payload=b'["ok"]'))
        self.assertEqual(result["unknown_count"], 1)

    def test_binary_invalid_utf8_rejected(self):
        result, _ = self.sample(response=Response(payload=b'\xff\x80'))
        self.assertEqual(result["unknown_count"], 1)

    def test_json_large_rejected(self):
        result, _ = self.sample(response=Response(payload=b'{"status":"ok","app":"Klone","x":"' + b'x' * 12000 + b'"}'))
        self.assertEqual(result["services"][0]["reason"], "response_too_large")

    def test_json_content_type_rejected(self):
        result, _ = self.sample(response=Response(ctype="text/html"))
        self.assertEqual(result["services"][0]["reason"], "invalid_content_type")

    def test_json_content_type_parameters(self):
        result, _ = self.sample(response=Response(ctype="application/json; charset=UTF-8"))
        self.assertEqual(result["reported_ok_count"], 1)

    def test_server_extra_fields_never_exported(self):
        result, _ = self.sample(response=Response(payload=b'{"status":"ok","app":"Klone","database_path":"secret/bedroom"}'))
        self.assertEqual(result["reported_ok_count"], 1)
        self.assertNotIn("secret/bedroom", json.dumps(result))

    def test_unknown_service_denied_before_transport(self):
        fac = Factory()
        with self.assertRaises(ValueError):
            collect_local_service_observations(service_ids=("http://169.254.169.254",),
                                               _connection_factory=fac)
        self.assertEqual(fac.opened, [])

    def test_duplicate_service_denied(self):
        with self.assertRaisesRegex(ValueError,"duplicate_local_service"):
            self.sample(("main-api","main-api"))

    def test_invalid_service_collection(self):
        for candidate in ("main-api", [], None if False else [12], ["main-api"] * 7):
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                self.sample(candidate)

    def test_timeout_invalid(self):
        for timeout in (0,99,3001,True,0.5):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                collect_local_service_observations(timeout_ms=timeout)

    def test_factory_invalid(self):
        with self.assertRaises(ValueError):
            collect_local_service_observations(_connection_factory=object())

    def test_output_is_bounded_and_no_html(self):
        report, _ = self.sample(("main-api","next-api","chat-ui"))
        self.assertLess(len(json.dumps(report)), 32768)
        self.assertNotIn("hostname", json.dumps(report))

    def test_order_independent_except_elapsed(self):
        a, _ = self.sample(("chat-ui", "main-api"))
        b, _ = self.sample(("main-api", "chat-ui"))
        self.assertEqual([x['service_id'] for x in a['services']],
                         [x['service_id'] for x in b['services']])

    def test_partial_failure_count(self):
        report, _ = self.sample(("chat-ui", "main-api"), Response(status=500))
        self.assertEqual(report["unavailable_count"], 2)
        self.assertEqual(report["reported_ok_count"], 0)

    def test_validate_report_does_not_claim_provenance(self):
        report, _ = self.sample()
        _validate_live_report(report)
        self.assertFalse(report["process_identity_authenticated"])

    def test_actual_loopback_http_transport(self):
        """True socket-level check with an ephemeral test-only local server."""
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path != '/api/health':
                    self.send_error(404)
                    return
                payload = b'{"status":"ok","app":"Klone","private":"not_for_export"}'
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *args):
                pass
        with ThreadingHTTPServer(('127.0.0.1', 0), Handler) as srv:
            thread = threading.Thread(target=srv.serve_forever, daemon=True)
            thread.start()
            from klone.mission_control_live_v32 import _Endpoint
            from klone import mission_control_live_v32 as mod
            with patch.dict(mod._BY_ID, {'main-api': _Endpoint('main-api', srv.server_port, '/api/health', 'klone_api')}):
                report = collect_local_service_observations(service_ids=('main-api',))
            srv.shutdown()
            thread.join(3)
        self.assertEqual(report['reported_ok_count'], 1)
        self.assertFalse(report['service_origin_authenticated'])
        self.assertNotIn('not_for_export', json.dumps(report))

    def test_validate_report_tamper_detected(self):
        report, _ = self.sample()
        report['reported_ok_count'] = 2
        with self.assertRaises(ValueError):
            _validate_live_report(report)

    def test_cli_requires_explicit_optin(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main([])


class CombinedLiveV31Tests(unittest.TestCase):
    def test_recalculates_v31_before_live_probe(self):
        event = PublicMemoryEvent(event_id=1, occurred_at=DATE, recorded_at=DATE)
        report = build_live_mission_control_review(
            expected_commit_sha=COMMIT, domain_states=dict.fromkeys(DOMAINS, 'unverified'),
            memory_before=[event], memory_after=[event],
            service_ids=('main-api',), _connection_factory=Factory())
        self.assertTrue(report['base_review_recomputed'])
        self.assertEqual(report['review_status'], 'manual_review_required')
        self.assertFalse(report['permission_granted'])

    def test_validation_fails_before_any_socket(self):
        factory=Factory()
        with self.assertRaises(ValueError):
            build_live_mission_control_review(
                expected_commit_sha=COMMIT, domain_states={'memory':'passed'},
                memory_before=[], memory_after=[], service_ids=('main-api',),
                _connection_factory=factory)
        self.assertEqual(factory.opened, [])

    def test_failing_live_response_propagates_hold(self):
        event = PublicMemoryEvent(event_id=1, occurred_at=DATE, recorded_at=DATE)
        report = build_live_mission_control_review(
            expected_commit_sha=COMMIT, domain_states=dict.fromkeys(DOMAINS, 'passed'),
            memory_before=[event], memory_after=[event],
            service_ids=('main-api',), _connection_factory=Factory(Response(status=503)))
        self.assertEqual(report['review_status'], 'blocked_for_review')


class OverlayTests(unittest.TestCase):
    def test_base_v31_integrates(self):
        live = collect_local_service_observations(service_ids=('main-api',), _connection_factory=Factory())
        report = compose_live_mission_control_review(sample_base(), live)
        self.assertEqual(report['review_status'], 'manual_review_required')
        self.assertFalse(report['deployment_approval'])
        self.assertFalse(report['base_review_recomputed'])
        self.assertFalse(report['service_identity_authenticated'])
        self.assertEqual(report['services_reported_ok'], 1)

    def test_unreachable_service_blocks(self):
        live = collect_local_service_observations(service_ids=('main-api',), _connection_factory=Factory(Response(status=404)))
        report = compose_live_mission_control_review(sample_base(), live)
        self.assertEqual(report['review_status'], 'blocked_for_review')
        self.assertIn('local_service_unavailable_or_unverified', report['review_reasons'])

    def test_missing_health_schema_blocks(self):
        live = collect_local_service_observations(service_ids=('main-api',), _connection_factory=Factory(Response(payload=b'{"status":"unknown"}')))
        report = compose_live_mission_control_review(sample_base(), live)
        self.assertEqual(report['review_status'], 'blocked_for_review')

    def test_existing_hold_cannot_be_upgraded(self):
        b = sample_base()
        b['review_status'] = 'blocked_for_review'
        from klone.mission_control_live_v32 import _canonical
        from hashlib import sha256
        d = {k:v for k,v in b.items() if k != 'report_sha256'}
        b['report_sha256'] = sha256(_canonical({'domain':'klone-v31-mission-control','report':d})).hexdigest()
        live = collect_local_service_observations(service_ids=('main-api',), _connection_factory=Factory())
        r = compose_live_mission_control_review(b,live)
        self.assertEqual(r['review_status'], 'blocked_for_review')

    def test_no_delegation_rights(self):
        r = compose_live_mission_control_review(sample_base(), collect_local_service_observations(
            service_ids=('main-api',), _connection_factory=Factory()))
        for key in ('permission_granted','tasks_dispatched','deployment_approval','production_readiness_verified'):
            self.assertFalse(r[key])

    def test_fake_base_digest_detected(self):
        base = sample_base()
        base['report_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError,'tampered_v31_review'):
            compose_live_mission_control_review(base,collect_local_service_observations(
                service_ids=('main-api',), _connection_factory=Factory()))

    def test_unknown_reason_not_exported(self):
        base = sample_base()
        base['review_reasons'].append('/private/key.txt')
        from klone.mission_control_live_v32 import _canonical
        from hashlib import sha256
        d={k:v for k,v in base.items() if k!='report_sha256'}
        base['report_sha256'] = sha256(_canonical({'domain':'klone-v31-mission-control','report':d})).hexdigest()
        with self.assertRaisesRegex(ValueError,'invalid_v31_review_reasons'):
            compose_live_mission_control_review(base,collect_local_service_observations(
                service_ids=('main-api',), _connection_factory=Factory()))

    def test_reject_fake_authorized_base(self):
        base = sample_base()
        base['permission_granted'] = True
        with self.assertRaises(ValueError):
            compose_live_mission_control_review(base,collect_local_service_observations(
                service_ids=('main-api',), _connection_factory=Factory()))

    def test_wrong_base_kind(self):
        base = sample_base()
        base['kind'] = 'hacked'
        with self.assertRaises(ValueError):
            compose_live_mission_control_review(base,collect_local_service_observations(
                service_ids=('main-api',), _connection_factory=Factory()))

    def test_report_is_bounded_and_no_source_content(self):
        report = compose_live_mission_control_review(sample_base(), collect_local_service_observations(
            service_ids=('main-api',), _connection_factory=Factory()))
        self.assertLess(len(json.dumps(report)), 65536)
        self.assertNotIn('raw_source',json.dumps(report))


if __name__ == '__main__':
    unittest.main()
