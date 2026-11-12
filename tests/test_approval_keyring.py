from datetime import datetime, timedelta, timezone
from hashlib import sha256
import hmac
import json
import unittest

from klone.approval_identity import SignedActorAssertion
from klone.approval_keyring import ApprovalKeyring, VerificationKey


class ApprovalKeyringTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 12, tzinfo=timezone.utc)
        self.epoch = int(self.now.timestamp())
        self.old = b"a" * 32
        self.new = b"b" * 32
        self.ring = ApprovalKeyring((
            VerificationKey("old", self.old, self.epoch - 600, self.epoch + 60),
            VerificationKey("new", self.new, self.epoch - 60, self.epoch + 600),
        ))

    def signed(self, secret):
        payload = json.dumps({
            "actor_id": "owner-1", "role": "owner",
            "room_id": "public_room", "issued_at": self.epoch,
        }).encode()
        return SignedActorAssertion(payload, hmac.new(secret, payload, sha256).hexdigest())

    def test_overlapping_rotation_keys(self):
        self.assertEqual(self.ring.verify("old", self.signed(self.old), now=self.now).role, "owner")
        self.assertEqual(self.ring.verify("new", self.signed(self.new), now=self.now).role, "owner")

    def test_wrong_key_denied(self):
        with self.assertRaisesRegex(PermissionError, "invalid_actor_signature"):
            self.ring.verify("new", self.signed(self.old), now=self.now)

    def test_unknown_key_denied(self):
        with self.assertRaisesRegex(PermissionError, "unknown_signing_key"):
            self.ring.verify("missing", self.signed(self.old), now=self.now)

    def test_expired_key_denied(self):
        later = self.now + timedelta(seconds=61)
        with self.assertRaisesRegex(PermissionError, "signing_key_inactive"):
            self.ring.verify("old", self.signed(self.old), now=later)

    def test_duplicate_key_id_denied(self):
        with self.assertRaisesRegex(ValueError, "invalid_keyring"):
            ApprovalKeyring((
                VerificationKey("same", self.old, 1, 10),
                VerificationKey("same", self.new, 1, 10),
            ))


if __name__ == "__main__":
    unittest.main()
