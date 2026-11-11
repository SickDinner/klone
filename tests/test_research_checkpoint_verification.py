from __future__ import annotations

from contextlib import closing
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3
import unittest

from klone.research_atomic_ledger import AtomicResearchLedger
from klone.research_checkpoint import make_checkpoint
from klone.research_checkpoint_anchor import advance_anchor
from klone.research_checkpoint_verification import verify_research_checkpoint
from klone.research_proposals import prepare_claim_proposal


class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "ledger.sqlite"
        self.key = b"s" * 32
        self.ledger = AtomicResearchLedger(self.path)
        self.ledger.commit_verified(
            proposal=prepare_claim_proposal(
                trace_id="trace-1", report_version=1, claim_id="claim-1",
                statement="First", source_refs=("doi:1",)),
            reviewer_id="owner", decision_reason="reviewed", authorized=True)
        self.checkpoint = make_checkpoint(database_path=self.path, key=self.key)
        self.anchor = advance_anchor(
            checkpoint=self.checkpoint, previous=None, expected_sequence=1)

    def verify(self, **changes):
        args = dict(database_path=self.path, checkpoint=self.checkpoint,
                    anchor=self.anchor, minimum_sequence=1, key=self.key)
        args.update(changes)
        return verify_research_checkpoint(**args)

    def test_valid_snapshot_and_anchor(self):
        result = self.verify()
        self.assertTrue(result.accepted)
        self.assertEqual(result.sequence, 1)

    def test_reject_wrong_key(self):
        self.assertFalse(self.verify(key=b"w" * 32).accepted)

    def test_reject_stale_external_sequence(self):
        self.assertFalse(self.verify(minimum_sequence=2).accepted)

    def test_reject_forged_anchor(self):
        self.assertFalse(self.verify(
            anchor=replace(self.anchor, anchor_digest="0" * 64)).accepted)

    def test_reject_modified_database(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE atomic_claims SET statement='forged'")
        self.assertFalse(self.verify().accepted)

    def test_reject_boolean_sequence(self):
        self.assertFalse(self.verify(minimum_sequence=True).accepted)


if __name__ == "__main__":
    unittest.main()
