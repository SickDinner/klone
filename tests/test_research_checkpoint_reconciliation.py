from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3
import unittest

from klone.research_anchor_registry import SqliteAnchorRegistry
from klone.research_atomic_ledger import AtomicResearchLedger
from klone.research_checkpoint_publisher import publish_checkpoint
from klone.research_proposals import prepare_claim_proposal


class PublicationReconciliationTests(unittest.TestCase):
    def test_orphan_claim_prevents_publication(self):
        with TemporaryDirectory() as tmp:
            ledger_path = Path(tmp) / "ledger.sqlite"
            registry = SqliteAnchorRegistry(Path(tmp) / "anchor.sqlite")
            ledger = AtomicResearchLedger(ledger_path)
            ledger.commit_verified(
                proposal=prepare_claim_proposal(
                    trace_id="trace-1", report_version=1, claim_id="claim-1",
                    statement="Evidence", source_refs=("doi:1",)),
                reviewer_id="owner", decision_reason="reviewed", authorized=True)
            with sqlite3.connect(ledger_path) as db:
                db.execute("DELETE FROM atomic_claim_audit")
            with self.assertRaisesRegex(ValueError, "inconsistent research ledger"):
                publish_checkpoint(
                    ledger_path=ledger_path, registry=registry, key=b"k" * 32)
            self.assertIsNone(registry.read())


if __name__ == "__main__":
    unittest.main()
