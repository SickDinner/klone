import unittest

from klone.acceptance_matrix import DOMAINS
from klone.unified_quality_gate import evaluate_quality_gate


class UnifiedQualityGateTests(unittest.TestCase):
    def setUp(self):
        self.sha = "a" * 40
        self.ci_run = {
            "id": 72, "run_attempt": 1, "head_sha": self.sha,
            "status": "completed", "conclusion": "success",
            "repository": {"full_name": "SickDinner/klone"},
        }
        self.ci_jobs = [
            {"run_id": 72, "name": "test", "status": "completed",
             "conclusion": "success"}
        ]
        self.termux = {
            "before": {"commit": self.sha, "dirty": False},
            "after": {"commit": self.sha, "dirty": False},
            "status": "passed", "exit_code": 0,
            "device_identity_verified": False,
        }

    def evaluate(self, **kwargs):
        return evaluate_quality_gate(
            repository="SickDinner/klone", commit=self.sha,
            ci_run=self.ci_run, ci_jobs=self.ci_jobs,
            required_ci_jobs={"test"}, **kwargs,
        )

    def test_ci_only_does_not_claim_android(self):
        result = self.evaluate()
        self.assertEqual(result["matrix"]["domains"]["android"], "unverified")
        self.assertFalse(result["ready_for_manual_review"])
        self.assertFalse(result["deployment_approval"])

    def test_all_non_deployment_domains_can_be_ready_for_review(self):
        states = {name: "passed" for name in DOMAINS
                  if name not in {"ci", "android", "deployment"}}
        result = self.evaluate(termux_report=self.termux, domain_states=states)
        self.assertTrue(result["ready_for_manual_review"])
        self.assertFalse(result["deployment_approval"])
        self.assertFalse(result["matrix"]["all_checks_passed"])

    def test_android_commit_mismatch_rejected(self):
        report = {**self.termux, "after": {"commit": "b" * 40, "dirty": False}}
        with self.assertRaises(ValueError):
            self.evaluate(termux_report=report)

    def test_reserved_domain_override_rejected(self):
        with self.assertRaises(ValueError):
            self.evaluate(domain_states={"deployment": "passed"})

    def test_failed_ci_rejected(self):
        self.ci_jobs[0]["conclusion"] = "failure"
        with self.assertRaises(ValueError):
            self.evaluate()
