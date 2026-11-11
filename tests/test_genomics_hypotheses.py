from __future__ import annotations
from dataclasses import replace
import unittest

from klone.genomics_hypotheses import EvidenceItem, Hypothesis, evaluate_hypotheses


def ev(evidence_id, stance="supports", group="paper-1"):
    return EvidenceItem(evidence_id, "doi:example", "h1", stance, "medium",
                        "Documented observation", group)


class GenomicsHypothesisTests(unittest.TestCase):
    def test_correlated_evidence_not_double_counted(self):
        result = evaluate_hypotheses(
            (Hypothesis("h1", "Historical hypothesis"),),
            (ev("a"), ev("b"), ev("c", "contradicts", "paper-2")))
        row = result["results"][0]
        self.assertEqual(row["support_groups"], 1)
        self.assertEqual(row["contradiction_groups"], 1)
        self.assertEqual(row["conclusion"], "insufficient_for_probability_or_causal_claim")

    def test_order_independent_fingerprint(self):
        h = (Hypothesis("h1", "Hypothesis"),)
        self.assertEqual(evaluate_hypotheses(h, (ev("a"), ev("b")))["fingerprint"],
                         evaluate_hypotheses(h, (ev("b"), ev("a")))["fingerprint"])

    def test_reject_duplicate_and_unlinked_evidence(self):
        h = (Hypothesis("h1", "Hypothesis"),)
        with self.assertRaises(ValueError):
            evaluate_hypotheses(h, (ev("a"), ev("a")))
        with self.assertRaises(ValueError):
            evaluate_hypotheses(h, (replace(ev("a"), hypothesis_id="unknown"),))
        with self.assertRaises(ValueError):
            evaluate_hypotheses(h, (replace(ev("a"), source_ref=""),))

    def test_empty_evidence_does_not_claim_truth(self):
        result = evaluate_hypotheses((Hypothesis("h1", "Hypothesis"),), ())
        self.assertEqual(result["results"][0]["support_groups"], 0)
        self.assertIn("insufficient", result["results"][0]["conclusion"])


if __name__ == "__main__":
    unittest.main()
