from __future__ import annotations

from contextlib import closing
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3
import unittest

from klone.research_atomic_ledger import AtomicResearchLedger
from klone.research_checkpoint import make_checkpoint, verify_checkpoint
from klone.research_proposals import prepare_claim_proposal


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "ledger.sqlite"
        self.key = b"a" * 32
        self.ledger = AtomicResearchLedger(self.path)
        self.proposal = prepare_claim_proposal(
            trace_id="trace-1", report_version=1, claim_id="claim-1",
            statement="A source-backed claim", source_refs=("doi:1",))
        self.ledger.commit_verified(
            proposal=self.proposal, reviewer_id="owner",
            decision_reason="approved", authorized=True)

    def test_valid_checkpoint(self):
        cp = make_checkpoint(database_path=self.path, key=self.key)
        self.assertEqual(cp.row_count, 2)
        self.assertTrue(verify_checkpoint(
            database_path=self.path, checkpoint=cp, key=self.key))
        self.assertEqual(cp, make_checkpoint(database_path=self.path, key=self.key))

    def test_tampered_database_detected(self):
        cp = make_checkpoint(database_path=self.path, key=self.key)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE atomic_claims SET statement='altered'")
        self.assertFalse(verify_checkpoint(
            database_path=self.path, checkpoint=cp, key=self.key))

    def test_forged_signature_and_wrong_key(self):
        cp = make_checkpoint(database_path=self.path, key=self.key)
        self.assertFalse(verify_checkpoint(
            database_path=self.path, checkpoint=cp, key=b"b" * 32))
        self.assertFalse(verify_checkpoint(
            database_path=self.path,
            checkpoint=replace(cp, signature="0" * 64), key=self.key))

    def test_missing_audit_detected(self):
        cp = make_checkpoint(database_path=self.path, key=self.key)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("DELETE FROM atomic_claim_audit")
        self.assertFalse(verify_checkpoint(
            database_path=self.path, checkpoint=cp, key=self.key))

    def test_weak_key_rejected(self):
        with self.assertRaises(ValueError):
            make_checkpoint(database_path=self.path, key=b"short")


if __name__ == "__main__":
    unittest.main()
