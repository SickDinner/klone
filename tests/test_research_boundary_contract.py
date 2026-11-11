from __future__ import annotations

from dataclasses import replace
import unittest

from klone.research_boundary_contract import (
    AuthenticatedSession, HypervisorGrant, prepare_research_write_intent,
)
from klone.research_proposals import prepare_claim_proposal


def fixture():
    proposal = prepare_claim_proposal(
        trace_id="trace-1", report_version=2, claim_id="claim-1",
        statement="Public statement", source_refs=("doi:1",))
    session = AuthenticatedSession("owner", "local-owner-session", "session-1", True)
    grant = HypervisorGrant("owner", "public-room", "research.claim.commit",
                            "trace-1", 2, 7, True)
    return proposal, session, grant


class ResearchBoundaryContractTests(unittest.TestCase):
    def test_exact_resource_bound_and_deterministic(self):
        proposal, session, grant = fixture()
        first = prepare_research_write_intent(proposal=proposal, session=session, grant=grant)
        self.assertEqual(first, prepare_research_write_intent(
            proposal=proposal, session=session, grant=grant))
        self.assertEqual(first.report_version, 2)
        self.assertEqual(len(first.fingerprint), 64)

    def test_spoofed_or_mismatched_assertions_denied(self):
        proposal, session, grant = fixture()
        for changed_session in (
            replace(session, verified=False),
            replace(session, issuer="request-header"),
            replace(session, principal="attacker"),
        ):
            with self.subTest(session=changed_session), self.assertRaises(PermissionError):
                prepare_research_write_intent(
                    proposal=proposal, session=changed_session, grant=grant)
        for changed_grant in (
            replace(grant, verified=False),
            replace(grant, room_id="sealed-room"),
            replace(grant, version=1),
            replace(grant, resource_id="trace-2"),
            replace(grant, action="research.claim.read"),
            replace(grant, policy_version=0),
        ):
            with self.subTest(grant=changed_grant), self.assertRaises(PermissionError):
                prepare_research_write_intent(
                    proposal=proposal, session=session, grant=changed_grant)

    def test_tampered_proposal_denied(self):
        proposal, session, grant = fixture()
        with self.assertRaises(ValueError):
            prepare_research_write_intent(
                proposal=replace(proposal, statement="forged"),
                session=session, grant=grant)


if __name__ == "__main__":
    unittest.main()
