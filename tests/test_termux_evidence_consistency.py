import unittest
from klone.termux_evidence_consistency import review_pinned_termux_result


class TermuxEvidenceConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.sha = "a" * 40
        self.report = {
            "before": {"commit": self.sha, "dirty": False},
            "after": {"commit": self.sha, "dirty": False},
            "status": "passed", "exit_code": 0,
            "device_identity_verified": False,
        }

    def verify(self, report):
        return review_pinned_termux_result(report, expected_commit=self.sha)

    def test_consistent_report_still_needs_review(self):
        result = self.verify(self.report)
        self.assertEqual(result["local_checkout_consistency"], "passed")
        self.assertFalse(result["deployment_approval"])
        self.assertTrue(result["manual_review_required"])

    def test_mismatch_and_failure_rejected(self):
        changes = [
            {"after": {"commit": "b" * 40, "dirty": False}},
            {"before": {"commit": self.sha, "dirty": True}},
            {"status": "failed"}, {"exit_code": 1},
            {"device_identity_verified": True}, {"after": None},
        ]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.verify({**self.report, **change})
