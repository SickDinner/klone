import unittest

from klone.acceptance_matrix import DOMAINS
from klone.development_priorities import prioritize_quality_work


class DevelopmentPrioritiesTests(unittest.TestCase):
    def setUp(self):
        self.states = dict.fromkeys(DOMAINS, "passed")

    def test_failure_beats_low_impact_pending(self):
        self.states["audit"] = "failed"
        self.states["media"] = "pending"
        result = prioritize_quality_work(self.states)
        self.assertEqual(result[0]["domain"], "audit")
        self.assertEqual(result[0]["priority_score"], 25)

    def test_deterministic_tie_break(self):
        self.states["ci"] = "unverified"
        self.states["audit"] = "unverified"
        self.assertEqual([r["domain"] for r in prioritize_quality_work(self.states)],
                         ["audit", "ci"])

    def test_all_passed_yields_no_work(self):
        self.assertEqual(prioritize_quality_work(self.states), [])

    def test_missing_domain_and_invalid_status_rejected(self):
        self.states.pop("memory")
        with self.assertRaises(ValueError):
            prioritize_quality_work(self.states)
        self.states["memory"] = "imaginary"
        with self.assertRaises(ValueError):
            prioritize_quality_work(self.states)
