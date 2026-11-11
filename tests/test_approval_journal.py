import sqlite3
import unittest

from klone.approval_policy import ApprovalProposal
from klone.approval_journal import ApprovalJournal


class ApprovalJournalTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:", isolation_level=None)
        self.journal = ApprovalJournal(self.connection)
        self.proposal = ApprovalProposal("p1", "agent", "public_room", "v1", "a" * 64)
        self.journal.propose(self.proposal, actor_id="agent")

    def tearDown(self):
        self.connection.close()

    def test_proposal_and_audit_created_atomically(self):
        self.assertEqual(self.journal.get("p1"), self.proposal)
        self.assertEqual([event.next_state for event in self.journal.events("p1")], ["proposed"])

    def test_valid_approval_audited(self):
        self.journal.transition("p1", "validated", actor_id="reviewer")
        self.journal.transition("p1", "awaiting_approval", actor_id="reviewer")
        approved = self.journal.transition(
            "p1", "approved", actor_id="human", human_approved=True,
            current_target_version="v1", current_patch_sha256="a" * 64,
        )
        self.assertEqual(approved.approver_id, "human")
        self.assertEqual(len(self.journal.events("p1")), 4)

    def test_invalid_transition_rolls_back(self):
        with self.assertRaises(ValueError):
            self.journal.transition("p1", "active", actor_id="agent")
        self.assertEqual(self.journal.get("p1").state, "proposed")
        self.assertEqual(len(self.journal.events("p1")), 1)

    def test_duplicate_proposal_does_not_duplicate_audit(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.journal.propose(self.proposal, actor_id="agent")
        self.assertEqual(len(self.journal.events("p1")), 1)

    def test_self_approval_denied_and_not_logged(self):
        self.journal.transition("p1", "validated", actor_id="agent")
        self.journal.transition("p1", "awaiting_approval", actor_id="agent")
        with self.assertRaises(PermissionError):
            self.journal.transition(
                "p1", "approved", actor_id="agent", human_approved=True,
                current_target_version="v1", current_patch_sha256="a" * 64,
            )
        self.assertEqual(len(self.journal.events("p1")), 3)

    def test_no_target_mutation(self):
        self.assertEqual(
            self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall(),
            [("approval_proposals",), ("approval_events",)],
        )


if __name__ == "__main__":
    unittest.main()
