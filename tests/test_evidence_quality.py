import unittest

from klone.evidence_quality import classify, report


def run(name, errors=(), integrity=False, passed=False, stage="unknown"):
    return {"run_name": name, "commit": "a" * 40, "errors": list(errors),
            "integrity_ok": integrity, "required_stages_passed": passed,
            "stage_statuses": {"syntax": stage, "cognition": stage,
                               "full": stage, "local_deploy": stage}}


class EvidenceQualityTests(unittest.TestCase):
    def test_verified_means_integrity_not_origin(self):
        entry = classify(run("good", integrity=True, passed=True, stage="passed"))
        self.assertEqual(entry["category"], "verified")
        self.assertFalse(entry["origin_authenticated"])
        self.assertFalse(entry["deployment_approval"])

    def test_missing_packet_incomplete(self):
        entry = classify(run("old", ["packet_unreadable: missing or oversized JSON"]))
        self.assertEqual(entry["category"], "incomplete")

    def test_mismatch_contradictory(self):
        entry = classify(run("bad", ["packet_mismatch"], integrity=False))
        self.assertEqual(entry["category"], "contradictory")

    def test_unknown_unexamined(self):
        self.assertEqual(classify(run("unknown"))["category"], "unexamined")

    def test_real_history_false_regression_is_unknown(self):
        runs = [
            run("verified-203503", ["packet_unreadable: missing"], passed=True,
                stage="passed"),
            run("verified-220158", ["packet_unreadable: missing", "run_invalid: missing"]),
        ]
        result = report(runs)
        self.assertEqual(result["categories"]["incomplete"], 2)
        self.assertEqual(result["confirmed_regression_transitions"], 0)
        self.assertGreater(result["unknown_transition_count"], 0)

    def test_verified_failure_is_not_approved(self):
        entry = classify(run("failed", integrity=True, stage="failed"))
        self.assertEqual(entry["category"], "verified")
        self.assertFalse(entry["required_stages_passed"])
        self.assertFalse(entry["deployment_approval"])


if __name__ == "__main__":
    unittest.main()
