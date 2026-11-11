from datetime import datetime, timezone
from hashlib import sha256
import hmac
import json
import unittest

from klone.approval_identity import SignedActorAssertion, verify_actor_assertion


class ApprovalIdentityTests(unittest.TestCase):
    def setUp(self):
        self.secret = b"s" * 32
        self.now = datetime(2026, 11, 11, tzinfo=timezone.utc)
        self.payload = json.dumps({
            "actor_id": "owner-1", "role": "owner",
            "room_id": "public_room", "issued_at": int(self.now.timestamp()),
        }, sort_keys=True).encode()

    def signed(self, payload=None):
        raw = self.payload if payload is None else payload
        return SignedActorAssertion(raw, hmac.new(self.secret, raw, sha256).hexdigest())

    def test_valid_signature_creates_verified_context(self):
        actor = verify_actor_assertion(self.signed(), secret=self.secret, now=self.now)
        self.assertTrue(actor.authenticated)
        self.assertEqual(actor.room_id, "public_room")

    def test_tampering_denied(self):
        assertion = self.signed()
        with self.assertRaisesRegex(PermissionError, "invalid_actor_signature"):
            verify_actor_assertion(
                SignedActorAssertion(assertion.payload + b" ", assertion.signature_hex),
                secret=self.secret, now=self.now,
            )

    def test_short_secret_denied(self):
        with self.assertRaises(PermissionError):
            verify_actor_assertion(self.signed(), secret=b"weak", now=self.now)

    def test_expired_denied(self):
        from datetime import timedelta
        with self.assertRaisesRegex(PermissionError, "invalid_actor_claims"):
            verify_actor_assertion(self.signed(), secret=self.secret, now=self.now + timedelta(minutes=6))

    def test_future_claim_denied(self):
        payload = self.payload.replace(
            str(int(self.now.timestamp())).encode(),
            str(int(self.now.timestamp()) + 30).encode(),
        )
        with self.assertRaises(PermissionError):
            verify_actor_assertion(self.signed(payload), secret=self.secret, now=self.now)

    def test_unknown_role_denied(self):
        payload = self.payload.replace(b'"owner"', b'"guest"')
        with self.assertRaises(PermissionError):
            verify_actor_assertion(self.signed(payload), secret=self.secret, now=self.now)


if __name__ == "__main__":
    unittest.main()
