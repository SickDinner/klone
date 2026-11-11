import sqlite3
from contextlib import closing
import tempfile
from pathlib import Path
import unittest

from klone.research_atomic_grant_commit import commit_claim_with_grant
from klone.research_atomic_ledger import AtomicResearchLedger
from klone.research_proposals import prepare_claim_proposal
from klone.research_signed_grants import issue_research_grant


class AtomicGrantCommitTests(unittest.TestCase):
    def test_commit_audit_and_nonce_atomic_with_replay_denial(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "ledger.sqlite"
            proposal = prepare_claim_proposal(
                trace_id="trace", report_version=1, claim_id="claim",
                statement="Claim", source_refs=("archive:1",))
            key = b"k" * 32
            grant = issue_research_grant(
                principal="reviewer", resource_id="claim", report_version=1,
                policy_version=2, expires_at=200, nonce="nonce-unique-123456",
                key=key)
            kwargs = dict(database_path=db, proposal=proposal, grant=grant,
                          principal="reviewer", policy_version=2, now=100,
                          key=key, decision_reason="Reviewed public evidence")
            receipt = commit_claim_with_grant(**kwargs)
            self.assertEqual(receipt.revision, 1)
            self.assertTrue(AtomicResearchLedger(db).verify(proposal.proposal_id))
            self.assertEqual(AtomicResearchLedger(db).reconcile(), ())
            with self.assertRaises(sqlite3.IntegrityError):
                commit_claim_with_grant(**kwargs)
            with closing(sqlite3.connect(db)) as conn:
                self.assertEqual(conn.execute(
                    "SELECT COUNT(*) FROM atomic_claims").fetchone()[0], 1)
                self.assertEqual(conn.execute(
                    "SELECT COUNT(*) FROM research_grant_nonces").fetchone()[0], 1)

    def test_invalid_policy_fails_without_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "ledger.sqlite"
            proposal = prepare_claim_proposal(
                trace_id="trace", report_version=1, claim_id="claim",
                statement="Claim", source_refs=("archive:1",))
            key = b"k" * 32
            grant = issue_research_grant(
                principal="reviewer", resource_id="claim", report_version=1,
                policy_version=2, expires_at=200, nonce="nonce-unique-123456",
                key=key)
            with self.assertRaises(PermissionError):
                commit_claim_with_grant(
                    database_path=db, proposal=proposal, grant=grant,
                    principal="reviewer", policy_version=3, now=100,
                    key=key, decision_reason="Reviewed")
            self.assertFalse(db.exists())


if __name__ == "__main__":
    unittest.main()
