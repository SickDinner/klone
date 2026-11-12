"""Offline security tests for the Termux bridge."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

FILE = Path(__file__).resolve().parents[1] / "tools" / "termux_bridge.py"
SPEC = importlib.util.spec_from_file_location("termux_bridge", FILE)
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)


class TermuxBridgeTests(unittest.TestCase):
    def test_allowlist_contains_no_arbitrary_shell(self):
        self.assertEqual(bridge.ALLOWED, {"status", "git_status", "tests", "health"})
        with self.assertRaises(ValueError):
            bridge.run_action("rm -rf /")

    def test_missing_checkout_prevents_action(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(bridge, "ROOT", Path(folder)):
                with self.assertRaises(RuntimeError):
                    bridge.run_action("tests")

    def test_only_trusted_issues_with_exact_json_are_executed(self):
        issues = [
            {"number": 1, "user": {"login": "intruder"}, "body": '{"action":"tests"}'},
            {"number": 2, "user": {"login": "owner"}, "body": '{"action":"tests","cmd":"rm"}'},
            {"number": 3, "user": {"login": "owner"}, "body": '{"action":"invalid"}'},
            {"number": 4, "user": {"login": "owner"}, "body": '{"action":"status"}'},
        ]
        calls = []

        def fake_api(method, path, payload=None):
            calls.append((method, path, payload))
            return issues if method == "GET" else {}

        with tempfile.TemporaryDirectory() as folder:
            with patch.dict("os.environ", {"KLONE_TRUSTED_ACTOR": "owner"}):
                with patch.object(bridge, "STATE", Path(folder) / "state.json"):
                    with patch.object(bridge, "api", side_effect=fake_api):
                        with patch.object(bridge, "run_action", return_value={"exit_code": 0, "output": "ok"}) as run:
                            bridge.once()
                            bridge.once()
        run.assert_called_once_with("status")
        self.assertEqual(len([x for x in calls if x[0] == "POST"]), 1)

    def test_result_summary_and_token_redaction(self):
        with patch.dict("os.environ", {"KLONE_GITHUB_TOKEN": "super-secret-token"}):
            message = bridge.format_result("tests", {
                "exit_code": 0,
                "output": "super-secret-token\nRan 531 tests in 34.257s\n\nOK (skipped=1)",
            })
        self.assertIn("Tests: 531 in 34.257s; OK (skipped=1)", message)
        self.assertIn("[REDACTED]", message)
        self.assertNotIn("super-secret-token", message)
        self.assertIn("Exit code: 0", message)

    def test_state_file_is_json_and_persists(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(bridge, "STATE", Path(folder) / "state.json"):
                bridge.save_state({"repo#3", "repo#2"})
                self.assertEqual(bridge.load_state(), {"repo#2", "repo#3"})
                self.assertEqual(json.loads(bridge.STATE.read_text()), ["repo#2", "repo#3"])


if __name__ == "__main__":
    unittest.main()
