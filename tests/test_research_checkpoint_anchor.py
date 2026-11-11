from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from klone.research_atomic_ledger import AtomicResearchLedger
from klone.research_checkpoint import make_checkpoint, LedgerCheckpoint
from klone.research_checkpoint_anchor import (
    advance_anchor, check_anchored_checkpoint,
)
from klone.research_proposals import prepare_claim_proposal


class AnchorTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "ledger.sqlite"
        self.ledger = AtomicResearchLedger(self.path)
        self.key = b"k" * 32
        self.ledger.commit_verified(
            proposal=prepare_claim_proposal(
                trace_id="trace-1", report_version=1, claim_id="claim-1",
                statement="First", source_refs=("doi:1",)),
            reviewer_id="owner", decision_reason="reviewed", authorized=True)

    def test_monotonic_chain_rejects_older_checkpoint(self):
        cp1 = make_checkpoint(database_path=self.path, key=self.key)
        a1 = advance_anchor(checkpoint=cp1, previous=None, expected_sequence=1)
        self.ledger.commit_verified(
            proposal=prepare_claim_proposal(
                trace_id="trace-1", report_version=1, claim_id="claim-2",
                statement="Second", source_refs=("doi:2",)),
            reviewer_id="owner", decision_reason="reviewed", authorized=True)
        cp2 = make_checkpoint(database_path=self.path, key=self.key)
        a2 = advance_anchor(checkpoint=cp2, previous=a1, expected_sequence=2)
        self.assertTrue(check_anchored_checkpoint(
            checkpoint=cp2, anchor=a2, minimum_sequence=2))
        self.assertFalse(check_anchored_checkpoint(
            checkpoint=cp1, anchor=a2, minimum_sequence=2))

    def test_forged_anchor_and_sequence_denied(self):
        cp = make_checkpoint(database_path=self.path, key=self.key)
        a1 = advance_anchor(checkpoint=cp, previous=None, expected_sequence=1)
        with self.assertRaises(ValueError):
            advance_anchor(checkpoint=cp, previous=a1, expected_sequence=1)
        with self.assertRaises(ValueError):
            advance_anchor(checkpoint=cp,
                           previous=replace(a1, checkpoint_digest="0" * 64),
                           expected_sequence=2)
        self.assertFalse(check_anchored_checkpoint(
            checkpoint=cp, anchor=replace(a1, sequence=2), minimum_sequence=1))
        self.assertFalse(check_anchored_checkpoint(
            checkpoint=cp, anchor=a1, minimum_sequence=2))


if __name__ == "__main__":
    unittest.main()
