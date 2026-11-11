from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from klone.research_anchor_registry import SqliteAnchorRegistry
from klone.research_atomic_ledger import AtomicResearchLedger
from klone.research_checkpoint_publisher import (
    publish_checkpoint, verify_published_checkpoint,
)
from klone.research_proposals import prepare_claim_proposal


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.ledger_path = Path(self.temp.name) / "ledger.sqlite"
        self.registry = SqliteAnchorRegistry(Path(self.temp.name) / "anchor.sqlite")
        self.key = b"k" * 32
        self.ledger = AtomicResearchLedger(self.ledger_path)
        self.append("claim-1", "First")

    def append(self, claim_id, statement):
        self.ledger.commit_verified(
            proposal=prepare_claim_proposal(
                trace_id="trace-1", report_version=1, claim_id=claim_id,
                statement=statement, source_refs=("doi:1",)),
            reviewer_id="owner", decision_reason="reviewed", authorized=True)

    def test_publish_and_verify(self):
        first = publish_checkpoint(
            ledger_path=self.ledger_path, registry=self.registry, key=self.key)
        self.assertEqual(first.anchor.sequence, 1)
        self.assertTrue(verify_published_checkpoint(
            ledger_path=self.ledger_path, registry=self.registry,
            publication=first, key=self.key))

    def test_new_write_invalidates_old_publication(self):
        first = publish_checkpoint(
            ledger_path=self.ledger_path, registry=self.registry, key=self.key)
        self.append("claim-2", "Second")
        self.assertFalse(verify_published_checkpoint(
            ledger_path=self.ledger_path, registry=self.registry,
            publication=first, key=self.key))
        second = publish_checkpoint(
            ledger_path=self.ledger_path, registry=self.registry, key=self.key)
        self.assertEqual(second.anchor.sequence, 2)
        self.assertTrue(verify_published_checkpoint(
            ledger_path=self.ledger_path, registry=self.registry,
            publication=second, key=self.key))
        self.assertFalse(verify_published_checkpoint(
            ledger_path=self.ledger_path, registry=self.registry,
            publication=first, key=self.key))

    def test_wrong_key_fails(self):
        first = publish_checkpoint(
            ledger_path=self.ledger_path, registry=self.registry, key=self.key)
        self.assertFalse(verify_published_checkpoint(
            ledger_path=self.ledger_path, registry=self.registry,
            publication=first, key=b"x" * 32))


if __name__ == "__main__":
    unittest.main()
