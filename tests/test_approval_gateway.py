from datetime import datetime, timedelta, timezone
from hashlib import sha256
import hmac
import json
import sqlite3
import unittest

from klone.approval_access import ApprovalAccess
from klone.approval_gateway import ApprovalGateway
from klone.approval_identity import SignedActorAssertion
from klone.approval_journal import ApprovalJournal
from klone.approval_policy import ApprovalProposal
from klone.approval_replay import AssertionReplayGuard


class ApprovalGatewayTests(unittest.TestCase):
    def test_signed_one_use_identity_to_approved_and_revoked(self):
        connection = sqlite3.connect(":memory:", isolation_level=None)
        journal = ApprovalJournal(connection)
        now = datetime(2026, 11, 11, tzinfo=timezone.utc)
        secret = b"k" * 32
        access = ApprovalAccess(
            journal, expires_at={"p1": now + timedelta(hours=1)},
        )
        gateway = ApprovalGateway(access, AssertionReplayGuard(connection), secret=secret)
        counter = 0

        def assertion(actor_id, role):
            nonlocal counter
            counter += 1
            # Each signed payload is unique and still within the five-minute window.
            payload = json.dumps({
                "actor_id": actor_id, "role": role, "room_id": "public_room",
                "issued_at": int(now.timestamp()) - counter,
            }).encode()
            return SignedActorAssertion(
                payload, hmac.new(secret, payload, sha256).hexdigest(),
            )

        proposal = ApprovalProposal("p1", "supervisor-1", "public_room", "v1", "a" * 64)
        gateway.propose(proposal, assertion=assertion("supervisor-1", "supervisor"), now=now)
        gateway.transition("p1", "validated", assertion=assertion("supervisor-1", "supervisor"), now=now)
        gateway.transition("p1", "awaiting_approval", assertion=assertion("supervisor-1", "supervisor"), now=now)
        approved = gateway.transition(
            "p1", "approved", assertion=assertion("owner-1", "owner"), now=now,
            current_target_version="v1", current_patch_sha256="a" * 64,
        )
        self.assertEqual(approved.approver_id, "owner-1")
        gateway.revoke(
            "p1", assertion=assertion("owner-1", "owner"), now=now, reason="withdrawn",
        )
        with self.assertRaisesRegex(PermissionError, "approval_revoked"):
            gateway.transition(
                "p1", "activating", assertion=assertion("owner-1", "owner"), now=now,
                current_target_version="v1", current_patch_sha256="a" * 64,
            )
        self.assertEqual(journal.events("p1")[-1].next_state, "revoked")
        connection.close()


if __name__ == "__main__":
    unittest.main()
