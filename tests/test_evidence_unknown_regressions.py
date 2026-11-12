import unittest

from klone.evidence_observatory import compare_history


def run(name, status, integrity):
    return {"run_name": name, "commit": "a" * 40,
            "integrity_ok": integrity,
            "stage_statuses": {"syntax": status, "cognition": "passed",
                               "full": "passed", "local_deploy": "passed"}}


class UnknownRegressionTests(unittest.TestCase):
    def test_missing_evidence_not_regression(self):
        changes = compare_history([
            run("verified-203503", "passed", False),
            run("verified-220158", "unknown", False),
        ])
        self.assertEqual(changes[0]["regressed_stages"], [])
        self.assertIn("syntax", changes[0]["unknown_transitions"])
        self.assertFalse(changes[0]["comparable"])

    def test_verified_pass_to_fail_is_regression(self):
        changes = compare_history([run("a", "passed", True),
                                   run("b", "failed", True)])
        self.assertIn("syntax", changes[0]["regressed_stages"])

    def test_unverified_pass_to_fail_not_confirmed(self):
        changes = compare_history([run("a", "passed", False),
                                   run("b", "failed", True)])
        self.assertEqual(changes[0]["regressed_stages"], [])
        self.assertIn("syntax", changes[0]["unknown_transitions"])

    def test_failed_to_passed_is_recovery_only_if_verified(self):
        changes = compare_history([run("a", "failed", True),
                                   run("b", "passed", True)])
        self.assertIn("syntax", changes[0]["recovered_stages"])


if __name__ == "__main__":
    unittest.main()
