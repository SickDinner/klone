from __future__ import annotations
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

from klone.research_proposals import prepare_claim_proposal, verify_claim_proposal, prepare_claim_review
from klone.research_memory import ResearchMemory
from klone.research_report import ResearchReport


class ClaimProposalTests(unittest.TestCase):
    def test_deterministic_and_no_persistence(self):
        arguments = dict(trace_id="trace", report_version=1, claim_id="c1",
                         statement="A claim", source_refs=("source:one",))
        first = prepare_claim_proposal(**arguments)
        second = prepare_claim_proposal(**arguments)
        self.assertEqual(first, second)
        self.assertEqual(len(first.proposal_id), 64)
        self.assertEqual(first.requested_status, "unverified")

    def test_proposal_id_changes_with_evidence_or_review(self):
        base = dict(trace_id="trace", report_version=1, claim_id="c1",
                    statement="A claim", source_refs=("source:one",))
        original = prepare_claim_proposal(**base)
        modified = (
            {"statement": "A different claim"},
            {"source_refs": ("source:two",)},
            {"report_version": 2},
            {"requested_status": "contested", "rationale": "Conflicting source"},
        )
        for changes in modified:
            with self.subTest(changes=changes):
                candidate = prepare_claim_proposal(**(base | changes))
                self.assertNotEqual(candidate.proposal_id, original.proposal_id)

    def test_verify_proposal_against_stored_public_report(self):
        with TemporaryDirectory() as directory:
            memory = ResearchMemory(Path(directory) / "reports.sqlite")
            memory.save(ResearchReport("trace", "public-room", "Question",
                                       "# Report", ("source:one",)))
            proposal = prepare_claim_proposal(
                trace_id="trace", report_version=1, claim_id="c1",
                statement="Claim", source_refs=("source:one",))
            self.assertTrue(verify_claim_proposal(proposal, memory=memory))
            with self.assertRaises(ValueError):
                verify_claim_proposal(replace(proposal, statement="Tampered"), memory=memory)
            absent = prepare_claim_proposal(
                trace_id="trace", report_version=1, claim_id="c1",
                statement="Claim", source_refs=("source:absent",))
            with self.assertRaises(ValueError):
                verify_claim_proposal(absent, memory=memory)
            missing_version = prepare_claim_proposal(
                trace_id="trace", report_version=2, claim_id="c1",
                statement="Claim", source_refs=("source:one",))
            with self.assertRaises(ValueError):
                verify_claim_proposal(missing_version, memory=memory)

    def test_review_decision_is_pure_and_requires_reason(self):
        proposal = prepare_claim_proposal(
            trace_id="trace", report_version=1, claim_id="c1",
            statement="Claim", source_refs=("source:one",))
        review = prepare_claim_review(
            proposal, reviewer_id="human-1", decision="reject",
            reason="Evidence is insufficient")
        self.assertEqual(review.proposal_id, proposal.proposal_id)
        self.assertEqual(review.decision, "reject")
        for kwargs in (
            {"reviewer_id": "", "decision": "approve", "reason": "Reviewed"},
            {"reviewer_id": "human-1", "decision": "approve", "reason": ""},
            {"reviewer_id": "human-1", "decision": "write", "reason": "Reviewed"},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                prepare_claim_review(proposal, **kwargs)
        with self.assertRaises(ValueError):
            prepare_claim_review(
                replace(proposal, statement="Modified"),
                reviewer_id="human-1", decision="approve", reason="Reviewed")

    def test_rejects_bad_inputs(self):
        valid = dict(trace_id="trace", report_version=1, claim_id="c1",
                     statement="A claim", source_refs=("source:one",))
        for changes in (
            {"report_version": True},
            {"source_refs": ()},
            {"source_refs": ["source:one"]},
            {"requested_status": "supported"},
            {"statement": ""},
            {"requested_status": None},
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
