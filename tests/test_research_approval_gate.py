from __future__ import annotations
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from klone.research_approval_gate import TrustedReviewer, check_approval_preflight
from klone.research_memory import ResearchMemory
from klone.research_report import ResearchReport
from klone.research_proposals import prepare_claim_proposal
from klone.research_review_bundle import prepare_review_bundle


class ApprovalGateTests(unittest.TestCase):
    def test_identity_permission_integrity_and_no_write(self):
        with TemporaryDirectory() as directory:
            memory = ResearchMemory(Path(directory) / "reports.sqlite")
            memory.save(ResearchReport("trace", "public-room", "Question",
                                       "# Report", ("doi:one",)))
            proposal = prepare_claim_proposal(
                trace_id="trace", report_version=1, claim_id="c1",
                statement="A claim", source_refs=("doi:one",))
            bundle = prepare_review_bundle(proposal=proposal, hypotheses=(), evidence=())
            trusted = TrustedReviewer("owner", "local-owner-session", True, True)
            kwargs = dict(proposal=proposal, bundle=bundle, memory=memory,
                          hypotheses=(), evidence=())
            ok = check_approval_preflight(**kwargs, reviewer=trusted)
            self.assertTrue(ok.allowed)
            self.assertIn("no_write", ok.reason)
            for reviewer in (
                replace(trusted, authenticated=False),
                replace(trusted, authorized_for_public_evidence=False),
                replace(trusted, authenticator="request-header"),
            ):
                with self.subTest(reviewer=reviewer):
                    self.assertFalse(check_approval_preflight(**kwargs, reviewer=reviewer).allowed)
            forged = replace(bundle, bundle_id="0" * 64)
            self.assertFalse(check_approval_preflight(
                **(kwargs | {"bundle": forged}), reviewer=trusted).allowed)
            missing = replace(proposal, report_version=2)
            with self.assertRaises(ValueError):
                check_approval_preflight(
                    **(kwargs | {"proposal": missing}), reviewer=trusted)


if __name__ == "__main__":
    unittest.main()
