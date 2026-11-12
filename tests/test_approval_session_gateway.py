from datetime import datetime, timedelta, timezone
from hashlib import sha256
import hmac
import json
import sqlite3
import unittest

from klone.approval_access import ApprovalAccess
from klone.approval_atomic_gateway import AtomicApprovalGateway
from klone.approval_journal import ApprovalJournal
from klone.approval_keyring import ApprovalKeyring, VerificationKey
from klone.approval_policy import ApprovalProposal
from klone.approval_session import SessionAssertion


class SessionGatewayIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:", isolation_level=None)
        self.journal = ApprovalJournal(self.connection)
        self.now = datetime(2026, 11, 12, tzinfo=timezone.utc)
        self.secret = b"r" * 32
        epoch = int(self.now.timestamp())
        self.gateway = AtomicApprovalGateway(
            ApprovalAccess(self.journal, expires_at={"p1": self.now + timedelta(hours=1)}),
            keyring=ApprovalKeyring((
                VerificationKey("k1", self.secret, epoch - 60, epoch + 600),
            )),
        )
        self.counter = 0

    def tearDown(self):
        self.connection.close()

    def assertion(self, actor_id="supervisor-1", role="supervisor", session_id="s1"):
        self.counter += 1
        payload = json.dumps({
            "actor_id": actor_id, "role": role, "room_id": "public_room",
            "session_id": session_id, "audience": "klone-approval",
            "issued_at": int(self.now.timestamp()) - self.counter,
        }).encode()
        signature = hmac.new(
            self.secret, b"klone-approval-session-v1\x00k1\x00" + payload, sha256,
        ).hexdigest()
        return SessionAssertion(payload, signature, "k1")

    def test_session_bound_approval_and_revocation(self):
        proposal = ApprovalProposal("p1", "supervisor-1", "public_room", "v1", "a" * 64)
        self.gateway.session_propose(
            proposal, assertion=self.assertion(), expected_session_id="s1", now=self.now,
        )
        self.gateway.session_transition(
            "p1", "validated", assertion=self.assertion(),
            expected_session_id="s1", now=self.now,
        )
        self.gateway.session_transition(
            "p1", "awaiting_approval", assertion=self.assertion(),
            expected_session_id="s1", now=self.now,
        )
        approved = self.gateway.session_transition(
            "p1", "approved", assertion=self.assertion("owner-1", "owner"),
            expected_session_id="s1", now=self.now,
            current_target_version="v1", current_patch_sha256="a" * 64,
        )
        self.assertEqual(approved.approver_id, "owner-1")
        self.gateway.session_revoke(
            "p1", assertion=self.assertion("owner-1", "owner"),
            expected_session_id="s1", now=self.now, reason="cancelled",
        )
        self.assertTrue(self.journal.is_revoked("p1"))

    def test_wrong_session_cannot_consume_assertion(self):
        assertion = self.assertion(session_id="s1")
        proposal = ApprovalProposal("p1", "supervisor-1", "public_room", "v1", "a" * 64)
        with self.assertRaises(PermissionError):
            self.gateway.session_propose(
                proposal, assertion=assertion, expected_session_id="s2", now=self.now,
            )
        self.gateway.session_propose(
            proposal, assertion=assertion, expected_session_id="s1", now=self.now,
        )


if __name__ == "__main__":
    unittest.main()
