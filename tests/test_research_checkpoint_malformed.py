from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from klone.research_atomic_ledger import AtomicResearchLedger
from klone.research_checkpoint import make_checkpoint, verify_checkpoint
from klone.research_proposals import prepare_claim_proposal


class MalformedCheckpointTests(unittest.TestCase):
    def test_malformed_checkpoint_fails_closed(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.sqlite"
            ledger = AtomicResearchLedger(path)
            ledger.commit_verified(
                proposal=prepare_claim_proposal(
                    trace_id="trace-1", report_version=1, claim_id="claim-1",
                    statement="Evidence", source_refs=("doi:1",)),
                reviewer_id="owner", decision_reason="reviewed", authorized=True)
            key = b"k" * 32
            good = make_checkpoint(database_path=path, key=key)
            self.assertTrue(verify_checkpoint(
                database_path=path, checkpoint=good, key=key))
            malformed = (
                replace(good, format_version=True),
                replace(good, row_count=True),
                replace(good, row_count=-1),
                replace(good, snapshot_sha256=None),
                replace(good, snapshot_sha256=42),
                replace(good, signature=None),
                replace(good, signature=42),
                replace(good, signature=""),
            )
            for item in malformed:
                with self.subTest(item=item):
                    self.assertFalse(verify_checkpoint(
                        database_path=path, checkpoint=item, key=key))


if __name__ == "__main__":
    unittest.main()
