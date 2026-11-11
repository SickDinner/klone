from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from klone.research_evidence import EvidenceLedger


class EvidenceLedgerTests(unittest.TestCase):
    def test_revisions_and_history(self):
        with TemporaryDirectory() as directory:
            ledger = EvidenceLedger(Path(directory) / "claims.sqlite")
            first = ledger.append(claim_id="c1", statement="A claim",
                                  source_refs=("file:1",))
            second = ledger.append(claim_id="c1", statement="Revised claim",
                                   source_refs=("file:1", "file:2"),
                                   status="contested", reason="Conflicting records")
            self.assertEqual((first.revision, second.revision), (1, 2))
            self.assertEqual([item.revision for item in ledger.history("c1")], [2, 1])
            self.assertEqual(ledger.history("missing"), ())

    def test_review_requires_provenance(self):
        with TemporaryDirectory() as directory:
            ledger = EvidenceLedger(Path(directory) / "claims.sqlite")
            with self.assertRaises(ValueError):
                ledger.append(claim_id="c1", statement="Claim", source_refs=(),
                              status="supported", reason="No sources")

    def test_tampering_detected(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "claims.sqlite"
            ledger = EvidenceLedger(path)
            ledger.append(claim_id="c1", statement="Original", source_refs=("source",))
            with closing(sqlite3.connect(path)) as connection:
                with connection:
                    connection.execute(
                    "UPDATE research_claim_revisions SET statement = 'Altered' WHERE claim_id = 'c1'")
            with self.assertRaises(ValueError):
                ledger.history("c1")


if __name__ == "__main__":
    unittest.main()
