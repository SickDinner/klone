import unittest

from klone.evidence_claims_ledger import ledger


class ClaimsLedgerTests(unittest.TestCase):
    def test_observations_not_origin_authenticated(self):
        result = ledger({"local": {"commit": "a" * 40, "integrity_ok": True},
                         "github": {"conclusion": "success"},
                         "comparison": {"consistent_claims": True}})
        self.assertEqual(result["decision"], "manual_review_required")
        self.assertEqual(len(result["observations"]), 3)
        self.assertTrue(all(not x["verified_origin"] for x in result["observations"]))
        self.assertFalse(result["deployment_approval"])

    def test_missing_comparison_blocks(self):
        self.assertEqual(ledger({})["decision"], "blocked")

    def test_explicit_failure_blocks(self):
        self.assertEqual(ledger({"comparison": {"consistent_claims": False}})["decision"],
                         "blocked")

    def test_non_object_rejected(self):
        with self.assertRaises(ValueError):
            ledger([])

    def test_malformed_sections_fail_closed(self):
        result = ledger({"local": [], "github": "untrusted", "comparison": []})
        self.assertEqual(result["observations"], [])
        self.assertEqual(result["decision"], "blocked")


if __name__ == "__main__":
    unittest.main()
