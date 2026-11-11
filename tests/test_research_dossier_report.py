import unittest
from dataclasses import replace

from klone.genomics_hypotheses import EvidenceItem, Hypothesis
from klone.research_dossier import build_dossier
from klone.research_dossier_report import render_dossier_markdown


class DossierReportTests(unittest.TestCase):
    def test_report_contains_sources_and_review_flags(self):
        h = (Hypothesis("h", "Candidate | uncertain"),)
        e = (EvidenceItem("e1", "archive:1", "h", "contradicts",
                          "high", "A record", "original"),)
        report = render_dossier_markdown(build_dossier(version=1, hypotheses=h,
                                                        evidence=e))
        self.assertIn("archive:1", report)
        self.assertIn("Candidate \\| uncertain", report)
        self.assertIn("Contradictions: h", report)
        self.assertIn("Human review required", report)

    def test_forged_digest_is_rejected(self):
        d = build_dossier(version=1, hypotheses=(Hypothesis("h", "Claim"),),
                          evidence=())
        with self.assertRaisesRegex(ValueError, "integrity"):
            render_dossier_markdown(replace(d, fingerprint="0" * 64))


if __name__ == "__main__":
    unittest.main()
