import sqlite3
from contextlib import closing
import tempfile
from pathlib import Path
from unittest import TestCase

from klone.research_memory import ResearchMemory
from klone.research_report import ResearchReport
from klone.research_proposals import prepare_claim_proposal
from klone.research_signed_grants import issue_research_grant
from klone.research_atomic_grant_commit import commit_claim_with_grant
from klone.research_transaction_report_gate import require_current_report_in_transaction


class TransactionReportGateTests(TestCase):
    def test_stale_report_fails_before_nonce_and_claim(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / "shared.sqlite"
            memory = ResearchMemory(db)
            report = ResearchReport("trace", "public-room", "Research",
                                    "# Research", ("source:1",))
            memory.save(report)
            proposal = prepare_claim_proposal(
                trace_id="trace", report_version=1, claim_id="claim",
                statement="Claim", source_refs=("source:1",))
            key = b"k" * 32
            grant = issue_research_grant(
                principal="reviewer", resource_id="claim", report_version=1,
                policy_version=1, expires_at=200, nonce="unique-nonce-123456",
                key=key)
            args = dict(
                database_path=db, proposal=proposal, grant=grant,
                principal="reviewer", policy_version=1, now=100,
                key=key, decision_reason="Review",
                transaction_guard=lambda connection:
                    require_current_report_in_transaction(connection, proposal))
            receipt = commit_claim_with_grant(**args)
            self.assertEqual(receipt.revision, 1)
            memory.save(report)
            with self.assertRaises(PermissionError):
                commit_claim_with_grant(**dict(args, grant=issue_research_grant(
                    principal="reviewer", resource_id="claim", report_version=1,
                    policy_version=1, expires_at=200, nonce="unique-nonce-234567",
                    key=key)))
            with closing(sqlite3.connect(db)) as connection:
                count = connection.execute(
                    "SELECT COUNT(*) FROM research_grant_nonces").fetchone()[0]
            self.assertEqual(count, 1)

    def test_missing_report_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / "shared.sqlite"
            proposal = prepare_claim_proposal(
                trace_id="trace", report_version=1, claim_id="claim",
                statement="Claim", source_refs=("source:1",))
            key = b"k" * 32
            grant = issue_research_grant(
                principal="reviewer", resource_id="claim", report_version=1,
                policy_version=1, expires_at=200, nonce="unique-nonce-123456",
                key=key)
            with self.assertRaises(sqlite3.OperationalError):
                commit_claim_with_grant(
                    database_path=db, proposal=proposal, grant=grant,
                    principal="reviewer", policy_version=1, now=100,
                    key=key, decision_reason="Review",
                    transaction_guard=lambda connection:
                        require_current_report_in_transaction(connection, proposal))
