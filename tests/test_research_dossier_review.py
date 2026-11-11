import unittest
from dataclasses import replace

from klone.genomics_hypotheses import EvidenceItem, Hypothesis
from klone.research_dossier import build_dossier
from klone.research_dossier_review import review_dossier


class DossierReviewTests(unittest.TestCase):
    def test_contradictions_and_shared_dependency_collisions(self):
        h = (Hypothesis("h1", "Candidate"), Hypothesis("h2", "Unknown"))
        e = (
            EvidenceItem("e1", "archive:1", "h1", "supports", "medium",
                         "Supports", "shared"),
            EvidenceItem("e2", "archive:2", "h1", "contradicts", "high",
                         "Contradicts", "shared"),
        )
        result = review_dossier(build_dossier(version=1, hypotheses=h, evidence=e))
        self.assertEqual(result.contradictions, ("h1",))
        self.assertEqual(result.unresolved, ("h2",))
        self.assertEqual(result.dependency_collisions, ("h1:shared",))
        self.assertEqual(result.conclusion, "manual_review_required")

    def test_modified_dossier_fails_closed(self):
        dossier = build_dossier(version=1, hypotheses=(Hypothesis("h", "Claim"),),
                                evidence=())
        with self.assertRaisesRegex(ValueError, "integrity"):
            review_dossier(replace(dossier, fingerprint="f" * 64))


if __name__ == "__main__":
    unittest.main()
