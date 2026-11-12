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
from klone.approval_session_revocation import SessionRevocationRegistry


class SessionRevocationTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:", isolation_level=None)
        self.now = datetime(2026, 11, 12, tzinfo=timezone.utc)
        self.secret = b"v" * 32
        self.journal = ApprovalJournal(self.connection)
        epoch = int(self.now.timestamp())
        self.gateway = AtomicApprovalGateway(
            ApprovalAccess(
                self.journal, expires_at={"p1": self.now + timedelta(hours=1)},
            ),
            keyring=ApprovalKeyring((
                VerificationKey("k", self.secret, epoch - 60, epoch + 600),
            )),
        )

    def tearDown(self):
        self.connection.close()

    def assertion(self):
        payload = json.dumps({
            "actor_id": "supervisor-1", "role": "supervisor",
            "room_id": "public_room", "session_id": "s1",
            "audience": "klone-approval", "issued_at": int(self.now.timestamp()),
        }).encode()
        signature = hmac.new(
            self.secret, b"klone-approval-session-v1\x00k\x00" + payload, sha256,
        ).hexdigest()
        return SessionAssertion(payload, signature, "k")

    def test_revoked_session_denies_valid_signed_proposal(self):
        self.gateway.session_revocations.revoke("s1", now=self.now, reason="logout")
        proposal = ApprovalProposal("p1", "supervisor-1", "public_room", "v1", "a" * 64)
        with self.assertRaisesRegex(PermissionError, "approval_session_revoked"):
            self.gateway.session_propose(
                proposal, assertion=self.assertion(),
                expected_session_id="s1", now=self.now,
            )
        self.assertIsNone(self.journal.get("p1"))

    def test_revocation_persists_on_same_database(self):
        registry = SessionRevocationRegistry(self.connection)
        registry.revoke("s1", now=self.now, reason="compromised")
        self.assertTrue(SessionRevocationRegistry(self.connection).is_revoked("s1"))
        with self.assertRaisesRegex(PermissionError, "session_already_revoked"):
            registry.revoke("s1", now=self.now, reason="again")

    def test_invalid_session_denied(self):
        with self.assertRaises(PermissionError):
            self.gateway.session_revocations.require_active("")


if __name__ == "__main__":
    unittest.main()
