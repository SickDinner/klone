import unittest

from klone.genomics_hypotheses import EvidenceItem, Hypothesis
from klone.research_dossier import build_dossier
from klone.research_dossier_benchmark import BenchmarkFixture, score_dossier


class DossierBenchmarkTests(unittest.TestCase):
    def test_perfect_fixture(self):
        h = (Hypothesis("h", "Candidate"),)
        e = (
            EvidenceItem("e1", "archive:1", "h", "supports", "medium", "A", "g"),
            EvidenceItem("e2", "archive:2", "h", "contradicts", "high", "B", "g"),
        )
        dossier = build_dossier(version=1, hypotheses=h, evidence=e)
        fixture = BenchmarkFixture(frozenset({"e1", "e2"}), frozenset({"h"}),
                                   frozenset({"h:g"}))
        score = score_dossier(dossier, fixture)
        self.assertEqual(tuple(vars(score).values()), (1.0,) * 6)

    def test_missing_evidence_is_penalized(self):
        dossier = build_dossier(version=1, hypotheses=(Hypothesis("h", "Claim"),),
                                evidence=())
        fixture = BenchmarkFixture(frozenset({"e1"}), frozenset(), frozenset())
        score = score_dossier(dossier, fixture)
        self.assertEqual(score.evidence_recall, 0.0)
        self.assertEqual(score.evidence_precision, 0.0)


if __name__ == "__main__":
    unittest.main()
