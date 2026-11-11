import unittest
from dataclasses import replace

from klone.genomics_hypotheses import EvidenceItem, Hypothesis
from klone.research_dossier import build_dossier, compare_dossiers


class ResearchDossierTests(unittest.TestCase):
    def test_contradiction_and_correction_remain_visible(self):
        hypotheses = (Hypothesis("h1", "Historical connection is supported"),)
        supporting = EvidenceItem("e1", "archive:1", "h1", "supports",
                                  "medium", "Primary record", "archive-1")
        contradicting = EvidenceItem("e2", "doi:2", "h1", "contradicts",
                                     "high", "Independent sample", "study-2")
        first = build_dossier(version=1, hypotheses=hypotheses,
                              evidence=(supporting,))
        second = build_dossier(version=2, hypotheses=hypotheses,
                               evidence=(supporting, contradicting))
        delta = compare_dossiers(first, second)
        self.assertEqual(delta["added_evidence"], ("e2",))
        self.assertEqual(delta["removed_evidence"], ())
        self.assertEqual(delta["old_evaluation"][0]["contradiction_groups"], 0)
        self.assertEqual(delta["new_evaluation"][0]["contradiction_groups"], 1)
        self.assertEqual(delta["new_evaluation"][0]["support_groups"], 1)

    def test_revised_source_is_not_silently_replaced(self):
        h = (Hypothesis("h", "Test"),)
        e = EvidenceItem("e", "source:1", "h", "supports", "low",
                         "Initial", "group-1")
        old = build_dossier(version=1, hypotheses=h, evidence=(e,))
        new = build_dossier(version=2, hypotheses=h, evidence=(
            replace(e, stance="uncertain", rationale="Correction"),))
        self.assertEqual(compare_dossiers(old, new)["revised_evidence"], ("e",))

    def test_forged_fingerprint_rejected(self):
        h = (Hypothesis("h", "Test"),)
        first = build_dossier(version=1, hypotheses=h, evidence=())
        second = build_dossier(version=2, hypotheses=h, evidence=())
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            compare_dossiers(replace(first, fingerprint="0" * 64), second)

    def test_independent_of_input_order(self):
        h = (Hypothesis("b", "B"), Hypothesis("a", "A"))
        a = build_dossier(version=1, hypotheses=h, evidence=())
        b = build_dossier(version=1, hypotheses=tuple(reversed(h)), evidence=())
        self.assertEqual(a.fingerprint, b.fingerprint)


if __name__ == "__main__":
    unittest.main()
