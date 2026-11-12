import unittest

from klone.acceptance_matrix import DOMAINS
from klone.quality_drift import compare_acceptance_snapshots


class QualityDriftTests(unittest.TestCase):
    def setUp(self):
        self.previous = {"commit": "a" * 40,
                         "domains": dict.fromkeys(DOMAINS, "unverified")}
        self.current = {"commit": "b" * 40,
                        "domains": dict.fromkeys(DOMAINS, "unverified")}

    def test_regression_from_passed(self):
        self.previous["domains"]["memory"] = "passed"
        self.current["domains"]["memory"] = "failed"
        result = compare_acceptance_snapshots(self.previous, self.current)
        self.assertEqual(result["regression_count"], 1)
        self.assertEqual(result["regressions"][0]["domain"], "memory")
        self.assertFalse(result["deployment_approval"])

    def test_progress_is_not_regression(self):
        self.current["domains"]["ci"] = "passed"
        result = compare_acceptance_snapshots(self.previous, self.current)
        self.assertEqual(result["regression_count"], 0)
        self.assertEqual(len(result["changes"]), 1)
        self.assertTrue(result["manual_review_required"])

    def test_no_change(self):
        result = compare_acceptance_snapshots(self.previous, self.current)
        self.assertFalse(result["manual_review_required"])

    def test_missing_domain_fails_closed(self):
        self.current["domains"].pop("genomics")
        with self.assertRaises(ValueError):
            compare_acceptance_snapshots(self.previous, self.current)
