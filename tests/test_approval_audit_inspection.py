import sqlite3
import unittest
from datetime import datetime, timezone

from klone.approval_audit_inspection import inspect_approval_audit
from klone.approval_journal import ApprovalJournal
from klone.approval_policy import ApprovalProposal


class AuditInspectionTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:", isolation_level=None)
        self.journal = ApprovalJournal(self.connection)
        self.journal.propose(
            ApprovalProposal("p1", "agent", "public_room", "v1", "a" * 64),
            actor_id="agent",
        )

    def tearDown(self):
        self.connection.close()

    def test_valid_creation(self):
        report = inspect_approval_audit(self.journal, "p1")
        self.assertTrue(report.valid)
        self.assertEqual(report.event_count, 1)

    def test_missing_proposal(self):
        self.assertEqual(
            inspect_approval_audit(self.journal, "unknown").issues,
            ("unknown_proposal",),
        )

    def test_detects_inconsistent_state(self):
        self.connection.execute(
            "UPDATE approval_proposals SET state='active' WHERE proposal_id='p1'"
        )
        self.assertIn(
            "state_event_mismatch",
            inspect_approval_audit(self.journal, "p1").issues,
        )

    def test_revocation_audit_consistent(self):
        self.journal.revoke(
            "p1", actor_id="owner", now=datetime(2026, 11, 12, tzinfo=timezone.utc),
            reason="cancelled",
        )
        self.assertTrue(inspect_approval_audit(self.journal, "p1").valid)


if __name__ == "__main__":
    unittest.main()
