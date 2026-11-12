import unittest
from klone.evidence_decision_dossier import build, render


def good_report():
    sha = "a" * 40
    return {
        "local": {"commit": sha, "integrity_ok": True,
                  "required_stages_passed": True},
        "github": {"commit": sha, "conclusion": "success"},
        "comparison": {"consistent_claims": True},
    }


class DecisionDossierTests(unittest.TestCase):
    def test_consistent_claims_require_manual_review(self):
        dossier = build(good_report())
        self.assertEqual(dossier["decision"], "manual_review_required")
        self.assertFalse(dossier["deployment_approval"])
        self.assertFalse(dossier["origin_authenticated"])

    def test_inconsistent_claims_block(self):
        report = good_report()
        report["comparison"]["consistent_claims"] = False
        dossier = build(report)
        self.assertEqual(dossier["decision"], "blocked")
        self.assertEqual(dossier["next_actions"][0]["kind"], "investigate_mismatch")

    def test_actions_are_manual_only(self):
        dossier = build(good_report())
        self.assertTrue(all(x["requires_human_approval"] for x in dossier["next_actions"]))

    def test_html_escapes_untrusted_action(self):
        dossier = build(good_report())
        dossier["next_actions"][0]["reason"] = "<script>alert(1)</script>"
        page = render(dossier)
        self.assertNotIn("<script>", page)
        self.assertIn("&lt;script&gt;", page)


if __name__ == "__main__":
    unittest.main()
