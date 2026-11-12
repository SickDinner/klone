"""Termux evidence adapter offline tests."""
import unittest

from klone.termux_evidence_adapter import normalize_termux_comment


class TermuxEvidenceAdapterTests(unittest.TestCase):
    def setUp(self):
        self.sha = "a" * 40
        self.comment = (
            "KLONE Termux bridge result for `tests`\n\n"
            "Tests: 531 in 34.257s; OK (skipped=1)\n\n"
            "```text\nRan 531 tests in 34.257s\n\nOK (skipped=1)\n```\n"
            "Exit code: 0"
        )

    def normalize(self, comment=None, action="tests"):
        return normalize_termux_comment(
            self.comment if comment is None else comment,
            action=action, issue_number=108, expected_commit=self.sha,
            observed_at="2026-11-12T16:00:00Z",
        )

    def test_tests_success(self):
        result = self.normalize()
        self.assertEqual(result["source"], "termux_bridge")
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["details"]["tests"], 531)

    def test_missing_summary_is_rejected(self):
        with self.assertRaises(ValueError):
            self.normalize("KLONE Termux bridge result for `tests`\nExit code: 0")

    def test_exit_code_conflict_is_rejected(self):
        with self.assertRaises(ValueError):
            self.normalize(self.comment.replace("Exit code: 0", "Exit code: 0\nExit code: 1"))

    def test_failed_test_run_is_failure(self):
        failed = self.comment.replace("OK (skipped=1)", "FAILED (failures=1)").replace(
            "Exit code: 0", "Exit code: 1")
        self.assertEqual(self.normalize(failed)["status"], "failure")

    def test_wrong_action_is_rejected(self):
        with self.assertRaises(ValueError):
            self.normalize(action="health")


if __name__ == "__main__":
    unittest.main()
