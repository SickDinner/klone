from __future__ import annotations
from dataclasses import replace
import unittest

from klone.genomics_hypotheses import EvidenceItem, Hypothesis
from klone.research_proposals import prepare_claim_proposal
from klone.research_review_bundle import prepare_review_bundle


def proposal(status="unverified", rationale=""):
    return prepare_claim_proposal(
        trace_id="trace", report_version=1, claim_id="c1",
        statement="A claim", source_refs=("doi:one",),
        requested_status=status, rationale=rationale)


def evidence(stance="supports"):
    return EvidenceItem("e1", "doi:one", "h1", stance, "medium",
                        "Observed result", "study-1")


class ReviewBundleTests(unittest.TestCase):
    def test_deterministic_handoff(self):
        arguments = dict(proposal=proposal(),
                         hypotheses=(Hypothesis("h1", "Hypothesis"),),
                         evidence=(evidence(),))
        first = prepare_review_bundle(**arguments)
        self.assertEqual(first, prepare_review_bundle(**arguments))
        self.assertEqual(first.disposition, "human_review_required")
        self.assertEqual(len(first.bundle_id), 64)

    def test_conflicting_evidence_flagged(self):
        result = prepare_review_bundle(
            proposal=proposal(),
            hypotheses=(Hypothesis("h1", "Hypothesis"),),
            evidence=(evidence("contradicts"),))
        self.assertIn("contradictory_evidence", result.risk_flags)
        self.assertIn("missing_support", result.risk_flags)

    def test_empty_evidence_and_privileged_review(self):
        result = prepare_review_bundle(
            proposal=proposal("supported", "Reviewer must verify"),
            hypotheses=(), evidence=())
        self.assertIn("no_evidence", result.risk_flags)
        self.assertIn("reviewed_status_requires_privileged_approval", result.risk_flags)

    def test_tampered_proposal_fails(self):
        with self.assertRaises(ValueError):
            prepare_review_bundle(
                proposal=replace(proposal(), statement="Altered"),
                hypotheses=(), evidence=())


if __name__ == "__main__":
    unittest.main()
