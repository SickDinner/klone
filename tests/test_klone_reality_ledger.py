"""Regression checks for the read-only KLONE Reality Ledger utility."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "klone_reality_ledger.py"
SPEC = importlib.util.spec_from_file_location("klone_reality_ledger_test_module", SCRIPT)
assert SPEC and SPEC.loader
ledger = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ledger)


class RealityLedgerTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name) / "checkout"
        self.root.mkdir()

    def put(self, path, text="x"):
        destination = self.root / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text, encoding="utf-8")

    def test_default_never_probes_local_network(self):
        with mock.patch.object(ledger, "_probe", side_effect=AssertionError("hidden probe")):
            report = ledger.inventory(self.root)
        self.assertEqual(report["schema"], "klone.reality_ledger.v1")
        self.assertFalse(report["tests_executed"])
        self.assertFalse(report["deployment_approved"])
        self.assertEqual({p["state"] for p in report["local_services"]}, {"not_probed"})

    def test_missing_or_partial_source_never_becomes_operational(self):
        self.put("src/klone/council72.py")
        report = ledger.inventory(self.root)
        council = next(x for x in report["capabilities"] if x["id"] == "council72")
        self.assertEqual(council["source_state"], "partial")
        self.assertEqual(council["test_state"], "not_in_checkout")
        self.assertEqual(council["execution_state"], "not_executed_by_reality_ledger")

    def test_sources_and_tests_exist_but_are_not_marked_passed(self):
        self.put("src/klone/art.py")
        self.put("tests/test_phase_v1_3.py")
        report = ledger.inventory(self.root)
        art = next(x for x in report["capabilities"] if x["id"] == "art")
        self.assertEqual(art["source_state"], "present")
        self.assertEqual(art["test_state"], "files_present")
        self.assertEqual(art["runtime_state"], "not_verified_by_file_inventory")

    def test_version_difference_is_not_silently_hidden(self):
        self.put("pyproject.toml", '[project]\nname="klone"\nversion="0.1.0"\n')
        self.put("src/klone/contracts.py", 'APP_VERSION = "0.2.0"\n')
        report = ledger.inventory(self.root)
        self.assertEqual(report["versions"], {"package": "0.1.0", "runtime": "0.2.0"})
        self.assertIn("package_version_differs_from_app_version", report["flags"])

    def test_malformed_version_files_do_not_crash(self):
        self.put("pyproject.toml", "<<invalid>>")
        self.put("src/klone/contracts.py", "APP_VERSION = ??")
        report = ledger.inventory(self.root)
        self.assertEqual(report["versions"], {"package": None, "runtime": None})

    def test_detects_stored_runtime_artifact_names_only_when_tracked(self):
        self.put("tmp_smoke.sqlite", "opaque")
        with mock.patch.object(ledger, "_git", side_effect=lambda root, *args:
                               "tmp_smoke.sqlite" if args[0] == "ls-files" else None):
            report = ledger.inventory(self.root)
        self.assertEqual(report["repository_artifacts_to_review"], ["tmp_smoke.sqlite"])
        self.assertIn("tracked_runtime_artifacts_require_content_review", report["flags"])

    def test_loopback_allowlist_does_not_follow_external_redirects(self):
        with self.assertRaises(ValueError):
            ledger._probe(8080, "/anything")
        with self.assertRaises(ValueError):
            ledger._probe(8000, "http://example.org")

    def test_probe_keeps_database_paths_and_diagnostic_bodies_private(self):
        response = mock.Mock()
        response.status = 200
        response.read.return_value = json.dumps({
            "status": "ok", "app_version": "0.2.0",
            "database_path": "/private/db.sqlite", "api_key": "DO_NOT_PRINT",
        }).encode("utf-8")
        connection = mock.Mock()
        connection.getresponse.return_value = response
        with mock.patch.object(ledger.http.client, "HTTPConnection", return_value=connection) as conn:
            outcome = ledger._probe(8000, "/api/health")
        self.assertEqual(outcome, {"state": "health_reported_ok", "http_status": 200,
                                   "app_version": "0.2.0"})
        self.assertNotIn("DO_NOT_PRINT", json.dumps(outcome))
        conn.assert_called_once_with("127.0.0.1", 8000, timeout=1.0)
        connection.request.assert_called_once()

    def test_redirect_is_unhealthy_and_never_followed(self):
        response = mock.Mock()
        response.status = 302
        response.read.return_value = b""
        connection = mock.Mock()
        connection.getresponse.return_value = response
        with mock.patch.object(ledger.http.client, "HTTPConnection", return_value=connection):
            outcome = ledger._probe(8031, "/api/health")
        self.assertEqual(outcome, {"state": "unhealthy", "http_status": 302})

    def test_html_escapes_untrusted_checkout_labels(self):
        report = ledger.inventory(self.root)
        report["checkout"]["branch"] = '<img src=x onerror="alert(1)">'
        page = ledger.as_html(report)
        self.assertIn("&lt;img", page)
        self.assertNotIn("<img", page)
        self.assertIn("Content-Security-Policy", page)
        self.assertIn("Ei testiajotodistus", page)

    def test_output_is_exclusive_and_stays_outside_checkout(self):
        path = Path(self.folder.name) / "reports" / "report.json"
        ledger._write_new(self.root, path, '{"ok":true}')
        self.assertEqual(path.read_text(encoding="utf-8"), '{"ok":true}')
        with self.assertRaises(FileExistsError):
            ledger._write_new(self.root, path, "overwrite")
        with self.assertRaises(ValueError):
            ledger._write_new(self.root, self.root / "report.json", "bad")
        self.assertFalse((self.root / "report.json").exists())

    def test_a_symlinked_source_is_not_counted(self):
        safe = Path(self.folder.name) / "outside.py"
        safe.write_text("def fake(): pass\n", encoding="utf-8")
        target = self.root / "src" / "klone" / "art.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            target.symlink_to(safe)
        except (NotImplementedError, OSError):
            self.skipTest("Symlink creation not supported")
        report = ledger.inventory(self.root)
        art = next(x for x in report["capabilities"] if x["id"] == "art")
        self.assertEqual(art["source_state"], "not_in_checkout")


if __name__ == "__main__":
    unittest.main()
