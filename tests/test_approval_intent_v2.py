import unittest
import hmac
import json
import secrets
from hashlib import sha256
from datetime import datetime, timezone

from klone.approval_intent_v2 import (
    SignedDraftIntent, make_intent_payload, verify_intent,
)


class ApprovalIntentTests(unittest.TestCase):
    def setUp(self):
        self.key = secrets.token_bytes(32)
        self.at = datetime.fromtimestamp(1000, timezone.utc)
        self.fields = dict(action="approve_draft", actor_id="alice", room_id="public-room",
                           proposal_id="proposal-1", target_version="v1",
                           patch_sha256="a"*64, reason="")
        payload = make_intent_payload(**self.fields, issued_at=1000,
                                      nonce="f"*32, ttl_seconds=120)
        self.intent = SignedDraftIntent(payload, hmac.new(self.key, payload, sha256).hexdigest())

    def verify(self, **updates):
        return verify_intent(self.intent, secret=self.key, now=self.at,
                             **{**self.fields, **updates})

    def test_valid_intent(self):
        self.assertEqual(len(self.verify()), 64)

    def test_wrong_key(self):
        with self.assertRaises(PermissionError):
            verify_intent(self.intent, secret=secrets.token_bytes(32),
                          now=self.at, **self.fields)

    def test_wrong_operation(self):
        with self.assertRaises(PermissionError):
            self.verify(action="revoke_draft")

    def test_other_proposal(self):
        with self.assertRaises(PermissionError):
            self.verify(proposal_id="proposal-2")

    def test_other_actor(self):
        with self.assertRaises(PermissionError):
            self.verify(actor_id="mallory")

    def test_other_room(self):
        with self.assertRaises(PermissionError):
            self.verify(room_id="restricted-room")

    def test_other_patch(self):
        with self.assertRaises(PermissionError):
            self.verify(patch_sha256="b"*64)

    def test_expired_and_future(self):
        for ts in (999, 1120):
            with self.subTest(ts=ts), self.assertRaises(PermissionError):
                verify_intent(self.intent, secret=self.key,
                              now=datetime.fromtimestamp(ts, timezone.utc), **self.fields)

    def test_signature_modified(self):
        wrong = SignedDraftIntent(self.intent.payload, "0"*64)
        with self.assertRaises(PermissionError):
            verify_intent(wrong, secret=self.key, now=self.at, **self.fields)

    def test_unknown_field_rejected(self):
        obj = json.loads(self.intent.payload)
        obj["publish_verified"] = True
        payload = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
        wrapped = SignedDraftIntent(payload, hmac.new(self.key, payload, sha256).hexdigest())
        with self.assertRaises(PermissionError):
            verify_intent(wrapped, secret=self.key, now=self.at, **self.fields)

    def test_revoke_reason_bound(self):
        fields = {**self.fields, "action": "revoke_draft", "reason": "Owner withdrawal"}
        payload = make_intent_payload(**fields, issued_at=1000,
                                      nonce="e"*32, ttl_seconds=120)
        intent = SignedDraftIntent(payload, hmac.new(self.key, payload, sha256).hexdigest())
        self.assertEqual(len(verify_intent(intent, secret=self.key, now=self.at, **fields)), 64)
        with self.assertRaises(PermissionError):
            verify_intent(intent, secret=self.key, now=self.at,
                          **{**fields, "reason": "Changed reason"})

    def test_no_activation_or_publish(self):
        for action in ("activating", "active", "publish_verified"):
            with self.subTest(action=action), self.assertRaises(ValueError):
                make_intent_payload(**{**self.fields, "action": action},
                                    issued_at=1000, nonce="d"*32)

    def test_bool_time_denied(self):
        with self.assertRaises(ValueError):
            make_intent_payload(**self.fields, issued_at=True, nonce="f"*32)


if __name__ == "__main__":
    unittest.main()
