from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from klone.research_evidence import EvidenceLedger
from klone.research_memory import ResearchMemory
from klone.research_report import ResearchReport


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

    def test_claim_refs_must_match_verified_report(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "reports.sqlite"
            memory = ResearchMemory(path)
            memory.save(ResearchReport("trace", "public-room", "Q", "# Evidence",
                                       ("source:one",)))
            ledger = EvidenceLedger(path)
            saved = ledger.append_from_report(
                memory=memory, trace_id="trace", version=1,
                claim_id="c1", statement="Test claim",
                source_refs=("source:one",))
            self.assertEqual(saved.revision, 1)
            self.assertEqual(saved.report_trace_id, "trace")
            self.assertEqual(saved.report_version, 1)
            self.assertEqual(ledger.history("c1")[0].report_version, 1)
            with self.assertRaises(ValueError):
                ledger.append_from_report(
                    memory=memory, trace_id="trace", version=1,
                    claim_id="c2", statement="Unsupported reference",
                    source_refs=("source:other",))

    def test_invalid_report_version_and_reference_type(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "reports.sqlite"
            memory = ResearchMemory(path)
            memory.save(ResearchReport("trace", "public-room", "Q", "# Evidence",
                                       ("source:one",)))
            ledger = EvidenceLedger(path)
            for bad_version in (True, 0, -1):
                with self.subTest(version=bad_version), self.assertRaises(ValueError):
                    ledger.append_from_report(
                        memory=memory, trace_id="trace", version=bad_version,
                        claim_id="c1", statement="Claim",
                        source_refs=("source:one",))
            with self.assertRaises(ValueError):
                ledger.append_from_report(
                    memory=memory, trace_id="trace", version=1,
                    claim_id="c1", statement="Claim",
                    source_refs=["source:one"])
            self.assertEqual(ledger.history("c1"), ())

    def test_report_provenance_tampering_detected(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "reports.sqlite"
            memory = ResearchMemory(path)
            memory.save(ResearchReport("trace", "public-room", "Q", "# Evidence",
                                       ("source:one",)))
            ledger = EvidenceLedger(path)
            ledger.append_from_report(
                memory=memory, trace_id="trace", version=1,
                claim_id="c1", statement="Claim", source_refs=("source:one",))
            with closing(sqlite3.connect(path)) as connection:
                with connection:
                    connection.execute(
                        "UPDATE research_claim_revisions SET report_version = 99 WHERE claim_id = 'c1'")
            with self.assertRaises(ValueError):
                ledger.history("c1")

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
