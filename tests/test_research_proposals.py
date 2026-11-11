from __future__ import annotations
import unittest

from klone.research_proposals import prepare_claim_proposal


class ClaimProposalTests(unittest.TestCase):
    def test_deterministic_and_no_persistence(self):
        arguments = dict(trace_id="trace", report_version=1, claim_id="c1",
                         statement="A claim", source_refs=("source:one",))
        first = prepare_claim_proposal(**arguments)
        second = prepare_claim_proposal(**arguments)
        self.assertEqual(first, second)
        self.assertEqual(len(first.proposal_id), 64)
        self.assertEqual(first.requested_status, "unverified")

    def test_rejects_bad_inputs(self):
        valid = dict(trace_id="trace", report_version=1, claim_id="c1",
                     statement="A claim", source_refs=("source:one",))
        for changes in (
            {"report_version": True},
            {"source_refs": ()},
            {"source_refs": ["source:one"]},
            {"requested_status": "supported"},
            {"statement": ""},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                prepare_claim_proposal(**(valid | changes))

    def test_reviewed_proposal_requires_rationale(self):
        item = prepare_claim_proposal(
            trace_id="trace", report_version=1, claim_id="c1",
            statement="A claim", source_refs=("source:one",),
            requested_status="contested", rationale="Two conflicting sources",
        )
        self.assertEqual(item.requested_status, "contested")


if __name__ == "__main__":
    unittest.main()
