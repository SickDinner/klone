from datetime import datetime, timedelta, timezone
import sqlite3
import unittest

from klone.approval_access import ApprovalAccess, VerifiedActor
from klone.approval_journal import ApprovalJournal
from klone.approval_policy import ApprovalProposal


class ApprovalAccessTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:", isolation_level=None)
        self.journal = ApprovalJournal(self.conn)
        self.now = datetime(2026, 11, 11, tzinfo=timezone.utc)
        self.proposal = ApprovalProposal("p1", "supervisor-1", "public_room", "v1", "a" * 64)
        self.supervisor = VerifiedActor("supervisor-1", "supervisor", "public_room", True)
        self.owner = VerifiedActor("owner-1", "owner", "public_room", True)
        self.access = ApprovalAccess(self.journal, expires_at={"p1": self.now + timedelta(hours=1)})
        self.access.propose(self.proposal, actor=self.supervisor)

    def tearDown(self):
        self.conn.close()

    def _awaiting(self):
        self.access.transition("p1", "validated", actor=self.supervisor, now=self.now)
        self.access.transition("p1", "awaiting_approval", actor=self.supervisor, now=self.now)

    def test_owner_can_approve_after_independent_proposal(self):
        self._awaiting()
        result = self.access.transition(
            "p1", "approved", actor=self.owner, now=self.now,
            current_target_version="v1", current_patch_sha256="a" * 64,
        )
        self.assertEqual(result.approver_id, "owner-1")

    def test_supervisor_cannot_approve(self):
        self._awaiting()
        with self.assertRaises(PermissionError):
            self.access.transition(
                "p1", "approved", actor=self.supervisor, now=self.now,
                current_target_version="v1", current_patch_sha256="a" * 64,
            )

    def test_unauthenticated_actor_denied(self):
        with self.assertRaises(PermissionError):
            self.access.transition("p1", "validated", actor=VerifiedActor("x", "owner", "public_room", False), now=self.now)

    def test_cross_room_denied(self):
        with self.assertRaises(PermissionError):
            self.access.transition("p1", "validated", actor=VerifiedActor("x", "owner", "sealed_room", True), now=self.now)

    def test_expired_approval_denied(self):
        self._awaiting()
        with self.assertRaisesRegex(PermissionError, "approval_expired"):
            self.access.transition(
                "p1", "approved", actor=self.owner, now=self.now + timedelta(hours=2),
                current_target_version="v1", current_patch_sha256="a" * 64,
            )

    def test_missing_expiry_denied(self):
        self._awaiting()
        self.access.expires_at.clear()
        with self.assertRaisesRegex(PermissionError, "approval_expiry_missing"):
            self.access.transition(
                "p1", "approved", actor=self.owner, now=self.now,
                current_target_version="v1", current_patch_sha256="a" * 64,
            )

    def test_naive_time_denied(self):
        with self.assertRaisesRegex(ValueError, "timezone_aware_time_required"):
            self.access.transition("p1", "validated", actor=self.supervisor, now=datetime(2026, 11, 11))


if __name__ == "__main__":
    unittest.main()
