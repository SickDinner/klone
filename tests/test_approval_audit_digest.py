import sqlite3
import unittest

from klone.approval_audit_digest import approval_audit_digest
from klone.approval_journal import ApprovalJournal
from klone.approval_policy import ApprovalProposal


class ApprovalAuditDigestTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:", isolation_level=None)
        self.journal = ApprovalJournal(self.connection)
        self.journal.propose(
            ApprovalProposal("p1", "agent", "public_room", "v1", "a" * 64),
            actor_id="agent",
        )

    def tearDown(self):
        self.connection.close()

    def test_digest_stable_across_reads(self):
        self.assertEqual(
            approval_audit_digest(self.journal, "p1"),
            approval_audit_digest(self.journal, "p1"),
        )
        self.assertEqual(len(approval_audit_digest(self.journal, "p1")), 64)

    def test_detects_inconsistent_history(self):
        self.connection.execute(
            "UPDATE approval_proposals SET state='active' WHERE proposal_id='p1'"
        )
        with self.assertRaisesRegex(ValueError, "approval_audit_inconsistent"):
            approval_audit_digest(self.journal, "p1")

    def test_audit_event_changes_digest(self):
        before = approval_audit_digest(self.journal, "p1")
        self.journal.transition("p1", "validated", actor_id="agent")
        self.assertNotEqual(before, approval_audit_digest(self.journal, "p1"))


if __name__ == "__main__":
    unittest.main()
