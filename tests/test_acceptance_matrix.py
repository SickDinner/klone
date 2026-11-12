import unittest
from klone.acceptance_matrix import DOMAINS, summarize_acceptance


class AcceptanceMatrixTests(unittest.TestCase):
    def test_all_passed_does_not_approve_deployment(self):
        result = summarize_acceptance(dict.fromkeys(DOMAINS, "passed"))
        self.assertTrue(result["all_checks_passed"])
        self.assertFalse(result["deployment_approval"])
        self.assertTrue(result["manual_review_required"])

    def test_unverified_domain_blocks_completion(self):
        results = dict.fromkeys(DOMAINS, "passed")
        results["genomics"] = "unverified"
        result = summarize_acceptance(results)
        self.assertFalse(result["all_checks_passed"])
        self.assertEqual(result["blocked_domains"], ["genomics"])

    def test_missing_domain_and_unknown_state_rejected(self):
        with self.assertRaises(ValueError):
            summarize_acceptance({"ci": "passed"})
        results = dict.fromkeys(DOMAINS, "passed")
        results["android"] = "maybe"
        with self.assertRaises(ValueError):
            summarize_acceptance(results)
