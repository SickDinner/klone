from datetime import datetime, timezone
from hashlib import sha256
import hmac
import json
import sqlite3
import unittest

from klone.approval_identity import SignedActorAssertion
from klone.approval_replay import AssertionReplayGuard


class ReplayGuardTests(unittest.TestCase):
    def test_single_use_survives_new_guard_instance(self):
        connection = sqlite3.connect(":memory:", isolation_level=None)
        now = datetime(2026, 11, 11, tzinfo=timezone.utc)
        secret = b"x" * 32
        payload = json.dumps({
            "actor_id": "owner-1", "role": "owner",
            "room_id": "public_room", "issued_at": int(now.timestamp()),
        }).encode()
        assertion = SignedActorAssertion(payload, hmac.new(secret, payload, sha256).hexdigest())
        first = AssertionReplayGuard(connection)
        self.assertEqual(
            first.verify_once(assertion, secret=secret, now=now).actor_id, "owner-1"
        )
        second = AssertionReplayGuard(connection)
        with self.assertRaisesRegex(PermissionError, "actor_assertion_replayed"):
            second.verify_once(assertion, secret=secret, now=now)
        connection.close()


if __name__ == "__main__":
    unittest.main()
