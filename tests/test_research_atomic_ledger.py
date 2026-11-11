from __future__ import annotations

from dataclasses import replace
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3
import unittest

from klone.research_atomic_ledger import AtomicResearchLedger
from klone.research_proposals import prepare_claim_proposal


def proposal(claim_id="claim-1"):
    return prepare_claim_proposal(
        trace_id="trace-1", report_version=1, claim_id=claim_id,
        statement="Public evidence only", source_refs=("doi:public",),
        requested_status="supported", rationale="Reviewed source")


class AtomicLedgerTests(unittest.TestCase):
    def test_atomic_commit_audit_and_revisions(self):
        with TemporaryDirectory() as folder:
            ledger = AtomicResearchLedger(Path(folder) / "db.sqlite")
            first = ledger.commit_verified(
                proposal=proposal(), reviewer_id="reviewer",
                decision_reason="Reviewed", authorized=True)
            self.assertEqual(first.revision, 1)
            self.assertTrue(ledger.verify(first.proposal_id))
            with self.assertRaises(ValueError):
                ledger.commit_verified(proposal=proposal(), reviewer_id="reviewer",
                                       decision_reason="Again", authorized=True)
            second = prepare_claim_proposal(
                trace_id="trace-1", report_version=1, claim_id="claim-1",
                statement="Revised claim", source_refs=("doi:public",))
            self.assertEqual(ledger.commit_verified(
                proposal=second, reviewer_id="reviewer",
                decision_reason="Revision", authorized=True).revision, 2)

    def test_deny_untrusted_and_tampered(self):
        with TemporaryDirectory() as folder:
            ledger = AtomicResearchLedger(Path(folder) / "db.sqlite")
            with self.assertRaises(PermissionError):
                ledger.commit_verified(proposal=proposal(), reviewer_id="r",
                                       decision_reason="x", authorized=False)
            with self.assertRaises(ValueError):
                ledger.commit_verified(proposal=replace(proposal(), statement="forged"),
                                       reviewer_id="r", decision_reason="x", authorized=True)
            self.assertFalse(Path(folder, "db.sqlite").exists())

    def test_audit_failure_rolls_back_claim(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "db.sqlite"
            ledger = AtomicResearchLedger(path)
            original = proposal()
            ledger.commit_verified(proposal=original, reviewer_id="r",
                                   decision_reason="x", authorized=True)
            with closing(sqlite3.connect(path)) as db, db:
                db.execute("""CREATE TRIGGER deny_audit BEFORE INSERT ON atomic_claim_audit
                              BEGIN SELECT RAISE(ABORT, 'audit blocked'); END""")
            next_proposal = proposal("claim-2")
            with self.assertRaises(sqlite3.IntegrityError):
                ledger.commit_verified(proposal=next_proposal, reviewer_id="r",
                                       decision_reason="x", authorized=True)
            with closing(sqlite3.connect(path)) as db, db:
                self.assertEqual(db.execute(
                    "SELECT COUNT(*) FROM atomic_claims WHERE claim_id='claim-2'"
                ).fetchone()[0], 0)

    def test_detect_tampered_audit(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "db.sqlite"
            ledger = AtomicResearchLedger(path)
            receipt = ledger.commit_verified(proposal=proposal(), reviewer_id="r",
                                             decision_reason="x", authorized=True)
            with closing(sqlite3.connect(path)) as db, db:
                db.execute("UPDATE atomic_claim_audit SET reviewer_id='attacker'")
            with self.assertRaises(ValueError):
                ledger.verify(receipt.proposal_id)


if __name__ == "__main__":
    unittest.main()
