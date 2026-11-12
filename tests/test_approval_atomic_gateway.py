from datetime import datetime, timedelta, timezone
from hashlib import sha256
import hmac
import json
import sqlite3
import unittest

from klone.approval_access import ApprovalAccess
from klone.approval_atomic_gateway import AtomicApprovalGateway
from klone.approval_identity import SignedActorAssertion
from klone.approval_journal import ApprovalJournal
from klone.approval_keyring import ApprovalKeyring, VerificationKey
from klone.approval_policy import ApprovalProposal


class AtomicGatewayTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:", isolation_level=None)
        self.journal = ApprovalJournal(self.conn)
        self.now = datetime(2026, 11, 12, tzinfo=timezone.utc)
        self.secret = b"z" * 32
        epoch = int(self.now.timestamp())
        ring = ApprovalKeyring((VerificationKey("k1", self.secret, epoch - 60, epoch + 600),))
        self.gateway = AtomicApprovalGateway(
            ApprovalAccess(self.journal, expires_at={"p1": self.now + timedelta(hours=1)}),
            keyring=ring,
        )
        self.counter = 0

    def tearDown(self):
        self.conn.close()

    def assertion(self, actor="supervisor-1", role="supervisor"):
        self.counter += 1
        payload = json.dumps({
            "actor_id": actor, "role": role, "room_id": "public_room",
            "issued_at": int(self.now.timestamp()) - self.counter,
        }).encode()
        return SignedActorAssertion(payload, hmac.new(self.secret, payload, sha256).hexdigest())

    def test_atomic_proposal_and_replay(self):
        assertion = self.assertion()
        proposal = ApprovalProposal("p1", "supervisor-1", "public_room", "v1", "a" * 64)
        self.gateway.propose(proposal, key_id="k1", assertion=assertion, now=self.now)
        self.assertIsNotNone(self.journal.deadline("p1"))
        with self.assertRaisesRegex(PermissionError, "actor_assertion_replayed_or_conflict"):
            self.gateway.transition("p1", "validated", key_id="k1", assertion=assertion, now=self.now)
        self.assertEqual(self.journal.get("p1").state, "proposed")

    def test_failed_transition_rolls_back_replay_marker(self):
        assertion = self.assertion()
        with self.assertRaisesRegex(ValueError, "unknown_proposal"):
            self.gateway.transition("missing", "validated", key_id="k1", assertion=assertion, now=self.now)
        proposal = ApprovalProposal("p1", "supervisor-1", "public_room", "v1", "a" * 64)
        self.gateway.propose(proposal, key_id="k1", assertion=assertion, now=self.now)
        self.assertEqual(self.journal.get("p1").state, "proposed")

    def test_owner_revocation_blocks_activation(self):
        proposal = ApprovalProposal("p1", "supervisor-1", "public_room", "v1", "a" * 64)
        self.gateway.propose(proposal, key_id="k1", assertion=self.assertion(), now=self.now)
        self.gateway.revoke("p1", key_id="k1", assertion=self.assertion("owner-1", "owner"),
                            now=self.now, reason="withdrawn")
        with self.assertRaisesRegex(PermissionError, "approval_revoked"):
            self.gateway.transition("p1", "validated", key_id="k1",
                                    assertion=self.assertion(), now=self.now)


if __name__ == "__main__":
    unittest.main()
