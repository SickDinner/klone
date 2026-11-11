from __future__ import annotations

from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3
import unittest

from klone.research_atomic_ledger import AtomicResearchLedger
from klone.research_proposals import prepare_claim_proposal


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "ledger.sqlite"
        self.ledger = AtomicResearchLedger(self.path)
        self.proposal = prepare_claim_proposal(
            trace_id="trace-1", report_version=1, claim_id="claim-1",
            statement="Public source statement", source_refs=("doi:1",))
        self.ledger.commit_verified(
            proposal=self.proposal, reviewer_id="reviewer",
            decision_reason="reviewed", authorized=True)

    def test_clean_ledger(self):
        self.assertEqual(self.ledger.reconcile(), ())

    def test_missing_audit(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("DELETE FROM atomic_claim_audit")
        self.assertEqual(self.ledger.reconcile(),
                         ("missing_audit:" + self.proposal.proposal_id,))

    def test_modified_audit(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE atomic_claim_audit SET reviewer_id='forged'")
        self.assertEqual(self.ledger.reconcile(),
                         ("audit_digest:" + self.proposal.proposal_id,))

    def test_orphan_audit(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("DELETE FROM atomic_claims")
        self.assertEqual(self.ledger.reconcile(),
                         ("orphan_audit:" + self.proposal.proposal_id,))

    def test_revision_gap(self):
        second = prepare_claim_proposal(
            trace_id="trace-1", report_version=1, claim_id="claim-1",
            statement="Revised statement", source_refs=("doi:1",))
        self.ledger.commit_verified(
            proposal=second, reviewer_id="reviewer",
            decision_reason="revision", authorized=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("DELETE FROM atomic_claim_audit WHERE proposal_id=?",
                       (self.proposal.proposal_id,))
            db.execute("DELETE FROM atomic_claims WHERE proposal_id=?",
                       (self.proposal.proposal_id,))
        problems = self.ledger.reconcile()
        self.assertIn("revision_gap:claim-1", problems)


if __name__ == "__main__":
    unittest.main()
