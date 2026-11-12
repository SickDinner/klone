import unittest

from klone.acceptance_matrix import DOMAINS
from klone.evidence_bound_review import evaluate_evidence_bound_review


class EvidenceBoundReviewTests(unittest.TestCase):
    def setUp(self):
        self.sha = "a" * 40
        self.run = {
            "id": 72, "run_attempt": 1, "head_sha": self.sha,
            "status": "completed", "conclusion": "success",
            "repository": {"full_name": "SickDinner/klone"},
        }
        self.jobs = [{"run_id": 72, "name": "test",
                      "status": "completed", "conclusion": "success"}]
        self.evidence = {
            domain: {"state": "unverified", "source": "", "reference": ""}
            for domain in DOMAINS
        }
        self.evidence["ci"] = {
            "state": "passed", "source": "github_actions", "reference": "run:72"
        }

    def evaluate(self, **kwargs):
        return evaluate_evidence_bound_review(
            repository="SickDinner/klone", commit=self.sha,
            ci_run=self.run, ci_jobs=self.jobs,
            required_ci_jobs={"test"},
            domain_evidence=kwargs.pop("evidence", self.evidence),
            **kwargs,
        )

    def test_ci_only_does_not_approve_deployment(self):
        result = self.evaluate()
        self.assertEqual(result["review"]["matrix"]["domains"]["android"],
                         "unverified")
        self.assertFalse(result["evidence_authenticated"])
        self.assertFalse(result["deployment_approval"])

    def test_mismatched_ci_run_reference_rejected(self):
        self.evidence["ci"]["reference"] = "run:73"
        with self.assertRaises(ValueError):
            self.evaluate()

    def test_android_claim_without_report_rejected(self):
        self.evidence["android"] = {
            "state": "passed", "source": "termux_bridge", "reference": "issue:72"
        }
        with self.assertRaises(ValueError):
            self.evaluate()

    def test_deployment_self_attestation_rejected(self):
        self.evidence["deployment"] = {
            "state": "passed", "source": "user", "reference": "claim:1"
        }
        with self.assertRaises(ValueError):
            self.evaluate()

    def test_domain_pass_requires_reference(self):
        self.evidence["memory"]["state"] = "passed"
        with self.assertRaises(ValueError):
            self.evaluate()

    def test_failed_ci_rejected(self):
        self.jobs[0]["conclusion"] = "failure"
        with self.assertRaises(ValueError):
            self.evaluate()
