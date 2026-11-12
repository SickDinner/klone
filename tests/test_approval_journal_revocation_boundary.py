import sqlite3
import unittest
from datetime import datetime, timezone

from klone.approval_journal import ApprovalJournal
from klone.approval_policy import ApprovalProposal


class JournalRevocationBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:", isolation_level=None)
        self.journal = ApprovalJournal(self.conn)
        self.journal.propose(
            ApprovalProposal("p1", "supervisor-1", "public_room", "v1", "a" * 64),
            actor_id="supervisor-1",
        )

    def tearDown(self):
        self.conn.close()

    def test_direct_journal_transition_cannot_bypass_revocation(self):
        self.journal.revoke(
            "p1", actor_id="owner-1",
            now=datetime(2026, 11, 12, tzinfo=timezone.utc), reason="cancelled",
        )
        with self.assertRaisesRegex(PermissionError, "approval_revoked"):
            self.journal.transition("p1", "validated", actor_id="supervisor-1")
        self.assertEqual(self.journal.get("p1").state, "proposed")
        self.assertEqual(len(self.journal.events("p1")), 2)

    def test_schema_revocation_table_exists(self):
        tables = {
            row[0] for row in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        self.assertIn("approval_revocations", tables)


if __name__ == "__main__":
    unittest.main()
