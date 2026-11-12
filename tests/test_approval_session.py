from datetime import datetime, timedelta, timezone
from hashlib import sha256
import hmac
import json
import unittest

from klone.approval_session import SessionAssertion, verify_session_assertion


class SessionAssertionTests(unittest.TestCase):
    def setUp(self):
        self.secret = b"q" * 32
        self.now = datetime(2026, 11, 12, tzinfo=timezone.utc)
        self.claims = {
            "actor_id": "owner-1", "role": "owner", "room_id": "public_room",
            "session_id": "session-123", "audience": "klone-approval",
            "issued_at": int(self.now.timestamp()),
        }

    def sign(self, claims=None, key_id="key-a"):
        payload = json.dumps(self.claims if claims is None else claims).encode()
        digest = hmac.new(
            self.secret, b"klone-approval-session-v1\x00" + key_id.encode()
            + b"\x00" + payload, sha256,
        ).hexdigest()
        return SessionAssertion(payload, digest, key_id)

    def verify(self, assertion, **kwargs):
        return verify_session_assertion(
            assertion, secret=self.secret, now=self.now,
            expected_session_id="session-123", **kwargs,
        )

    def test_valid_session(self):
        self.assertEqual(self.verify(self.sign()).actor_id, "owner-1")

    def test_wrong_session_denied(self):
        changed = dict(self.claims, session_id="session-other")
        with self.assertRaisesRegex(PermissionError, "invalid_session_claims"):
            self.verify(self.sign(changed))

    def test_wrong_audience_denied(self):
        changed = dict(self.claims, audience="another-service")
        with self.assertRaises(PermissionError):
            self.verify(self.sign(changed))

    def test_tampered_payload_denied(self):
        signed = self.sign()
        with self.assertRaisesRegex(PermissionError, "invalid_session_signature"):
            self.verify(SessionAssertion(signed.payload + b" ", signed.signature_hex, signed.key_id))

    def test_wrong_key_id_denied(self):
        signed = self.sign()
        with self.assertRaises(PermissionError):
            self.verify(SessionAssertion(signed.payload, signed.signature_hex, "key-b"))

    def test_expired_session_denied(self):
        changed = dict(self.claims, issued_at=int(self.now.timestamp()) - 121)
        with self.assertRaises(PermissionError):
            self.verify(self.sign(changed))

    def test_future_session_denied(self):
        changed = dict(self.claims, issued_at=int(self.now.timestamp()) + 1)
        with self.assertRaises(PermissionError):
            self.verify(self.sign(changed))


if __name__ == "__main__":
    unittest.main()
