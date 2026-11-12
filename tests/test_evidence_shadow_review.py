import unittest
from klone.evidence_shadow_review import review


def report(valid=True):
    commit = "a" * 40
    return {"local": {"commit": commit, "integrity_ok": valid,
                      "required_stages_passed": valid},
            "github": {"commit": commit, "conclusion": "success"},
            "comparison": {"consistent_claims": valid}}


class ShadowReviewTests(unittest.TestCase):
    def test_four_reviewers_and_no_approval(self):
        result = review(report())
        self.assertEqual(len(result["reviewers"]), 4)
        self.assertTrue(result["operational_claims_consistent"])
        self.assertEqual(result["decision"], "manual_review_required")
        self.assertFalse(result["deployment_approval"])
        self.assertFalse(result["origin_authenticated"])

    def test_local_integrity_blocks(self):
        self.assertEqual(review(report(False))["decision"], "blocked")

    def test_missing_github_blocks(self):
        value = report()
        value["github"] = None
        self.assertEqual(review(value)["decision"], "blocked")

    def test_wrong_commit_blocks(self):
        value = report()
        value["github"]["commit"] = "b" * 40
        self.assertEqual(review(value)["decision"], "blocked")

    def test_missing_consistency_blocks(self):
        value = report()
        value["comparison"] = {}
        self.assertEqual(review(value)["decision"], "blocked")


if __name__ == "__main__":
    unittest.main()
