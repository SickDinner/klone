"""Synthetic-only tests for v3.5 signed identity and audit receipts."""
from __future__ import annotations

import base64
import copy
import unittest
import uuid

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from klone.service_identity_receipts_v35 import (
    ReceiptError, TrustedObserverKey, canonical_json, parse_receipt_json, receipt_sha256,
    verify_audit_chain, verify_audit_receipt, verify_service_identity_receipt,
)


NOW = 1_800_000_000
NONCE = "n" * 32
COMMIT = "a" * 40
PRIVATE = Ed25519PrivateKey.from_private_bytes(b"k" * 32)
PUBLIC = PRIVATE.public_key().public_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PublicFormat.Raw,
)
KEYS = {"test-observer-1": TrustedObserverKey("termux-observer", PUBLIC)}


def signed(receipt_type, subject, *, nonce=NONCE, issued_at=NOW, ttl=120,
           key=PRIVATE, receipt_id=None):
    body = {
        "schema_version": 1, "domain": "klone-service-audit-receipt-v1",
        "receipt_type": receipt_type,
        "receipt_id": receipt_id or str(uuid.uuid4()),
        "issuer": "termux-observer", "key_id": "test-observer-1",
        "issued_at": issued_at, "expires_at": issued_at + ttl,
        "nonce": nonce, "subject": subject,
    }
    signature = base64.urlsafe_b64encode(key.sign(canonical_json(body))).decode().rstrip("=")
    return {"body": body, "signature": signature}


def identity_subject(**changes):
    result = {
        "service_id": "main-api", "pid": 4132, "process_start_time_ns": 123456789,
        "owner_uid": 10001, "executable_sha256": "b" * 64,
        "command_sha256": "c" * 64, "listen_host": "127.0.0.1",
        "listen_port": 8000, "application_commit_sha": COMMIT,
        "observer_id": "termux-procfs-v1",
    }
    result.update(changes)
    return result


def audit_subject(identity, *, previous="0" * 64, event_time=NOW, **changes):
    result = {
        "event_id": str(uuid.uuid4()), "actor_service_id": identity.service_id,
        "actor_identity_receipt_sha256": identity.receipt_sha256,
        "action": "health.read", "resource_type": "service", "resource_id": "main-api",
        "outcome": "allowed", "event_time": event_time,
        "request_sha256": "d" * 64, "previous_receipt_sha256": previous,
    }
    result.update(changes)
    return result


def verified_identity(receipt=None):
    receipt = receipt or signed("service_identity", identity_subject())
    return verify_service_identity_receipt(
        receipt, trusted_public_keys=KEYS, expected_nonce=NONCE,
        expected_service_id="main-api", expected_commit_sha=COMMIT, now=NOW,
    )


class ServiceIdentityReceiptV35Tests(unittest.TestCase):
    def test_valid_identity_claim_is_bound_to_nonce_service_and_commit(self):
        receipt = signed("service_identity", identity_subject())
        result = verified_identity(receipt)
        self.assertEqual(result.service_id, "main-api")
        self.assertEqual(result.application_commit_sha, COMMIT)
        self.assertFalse(result.live_process_rechecked)
        self.assertEqual(result.receipt_sha256, receipt_sha256(receipt))

    def test_modified_body_is_rejected(self):
        receipt = signed("service_identity", identity_subject())
        receipt["body"]["subject"]["pid"] += 1
        with self.assertRaisesRegex(ReceiptError, "signature_invalid"):
            verified_identity(receipt)

    def test_unknown_key_is_rejected(self):
        receipt = signed("service_identity", identity_subject())
        receipt["body"]["key_id"] = "attacker-key"
        with self.assertRaisesRegex(ReceiptError, "untrusted_key_id"):
            verified_identity(receipt)

    def test_trusted_key_cannot_claim_another_issuer_name(self):
        receipt = signed("service_identity", identity_subject())
        receipt["body"]["issuer"] = "different-observer"
        receipt["signature"] = base64.urlsafe_b64encode(
            PRIVATE.sign(canonical_json(receipt["body"]))
        ).decode().rstrip("=")
        with self.assertRaisesRegex(ReceiptError, "untrusted_issuer"):
            verified_identity(receipt)

    def test_nonce_replay_is_rejected(self):
        receipt = signed("service_identity", identity_subject(), nonce="x" * 32)
        with self.assertRaisesRegex(ReceiptError, "nonce_mismatch"):
            verified_identity(receipt)

    def test_expired_and_future_receipts_are_rejected(self):
        expired = signed("service_identity", identity_subject(), issued_at=NOW - 200, ttl=100)
        with self.assertRaisesRegex(ReceiptError, "receipt_expired"):
            verify_service_identity_receipt(
                expired, trusted_public_keys=KEYS, expected_nonce=NONCE,
                expected_service_id="main-api", expected_commit_sha=COMMIT, now=NOW,
            )
        future = signed("service_identity", identity_subject(), issued_at=NOW + 60)
        with self.assertRaisesRegex(ReceiptError, "receipt_from_future"):
            verify_service_identity_receipt(
                future, trusted_public_keys=KEYS, expected_nonce=NONCE,
                expected_service_id="main-api", expected_commit_sha=COMMIT, now=NOW,
            )

    def test_wrong_service_or_commit_is_rejected(self):
        receipt = signed("service_identity", identity_subject())
        with self.assertRaisesRegex(ReceiptError, "service_id_mismatch"):
            verify_service_identity_receipt(
                receipt, trusted_public_keys=KEYS, expected_nonce=NONCE,
                expected_service_id="chat-ui", expected_commit_sha=COMMIT, now=NOW,
            )
        with self.assertRaisesRegex(ReceiptError, "application_commit_mismatch"):
            verify_service_identity_receipt(
                receipt, trusted_public_keys=KEYS, expected_nonce=NONCE,
                expected_service_id="main-api", expected_commit_sha="f" * 40, now=NOW,
            )

    def test_non_loopback_identity_is_rejected(self):
        receipt = signed("service_identity", identity_subject(listen_host="0.0.0.0"))
        with self.assertRaisesRegex(ReceiptError, "non_loopback_service_identity"):
            verified_identity(receipt)

    def test_boolean_pid_and_extra_fields_are_rejected(self):
        receipt = signed("service_identity", identity_subject(pid=True))
        with self.assertRaisesRegex(ReceiptError, "invalid_process_id"):
            verified_identity(receipt)
        receipt = signed("service_identity", {**identity_subject(), "extra": "x"})
        with self.assertRaisesRegex(ReceiptError, "invalid_service_identity_subject"):
            verified_identity(receipt)

    def test_duplicate_json_keys_are_rejected(self):
        with self.assertRaisesRegex(ReceiptError, "duplicate_json_key"):
            parse_receipt_json('{"body":{},"body":{},"signature":"x"}')

    def test_valid_audit_receipt_is_bound_to_identity(self):
        identity_receipt = signed("service_identity", identity_subject())
        identity = verified_identity(identity_receipt)
        receipt = signed("audit_event", audit_subject(identity))
        event = verify_audit_receipt(
            receipt, trusted_public_keys=KEYS, identity_receipt=identity_receipt,
            expected_service_id="main-api", expected_commit_sha=COMMIT,
            expected_nonce=NONCE, now=NOW,
        )
        self.assertEqual(event["actor_service_id"], "main-api")
        self.assertEqual(event["action"], "health.read")

    def test_audit_event_from_different_identity_is_rejected(self):
        identity_receipt = signed("service_identity", identity_subject())
        identity = verified_identity(identity_receipt)
        receipt = signed("audit_event", audit_subject(identity, actor_service_id="chat-ui"))
        with self.assertRaisesRegex(ReceiptError, "audit_actor_mismatch"):
            verify_audit_receipt(
                receipt, trusted_public_keys=KEYS, identity_receipt=identity_receipt,
                expected_service_id="main-api", expected_commit_sha=COMMIT,
                expected_nonce=NONCE, now=NOW,
            )

    def test_audit_event_cannot_swap_identity_receipt(self):
        identity = verified_identity()
        receipt = signed("audit_event", audit_subject(
            identity, actor_identity_receipt_sha256="e" * 64,
        ))
        with self.assertRaisesRegex(ReceiptError, "audit_identity_receipt_mismatch"):
            verify_audit_receipt(
                receipt, trusted_public_keys=KEYS,
                identity_receipt=signed("service_identity", identity_subject()),
                expected_service_id="main-api", expected_commit_sha=COMMIT,
                expected_nonce=NONCE, now=NOW,
            )

    def test_audit_verifier_rechecks_original_signed_identity(self):
        identity_receipt = signed("service_identity", identity_subject())
        identity = verified_identity(identity_receipt)
        audit = signed("audit_event", audit_subject(identity))
        tampered_identity = copy.deepcopy(identity_receipt)
        tampered_identity["body"]["subject"]["pid"] += 1
        with self.assertRaisesRegex(ReceiptError, "signature_invalid"):
            verify_audit_receipt(
                audit, trusted_public_keys=KEYS,
                identity_receipt=tampered_identity,
                expected_service_id="main-api", expected_commit_sha=COMMIT,
                expected_nonce=NONCE, now=NOW,
            )

    def test_ordered_audit_chain_verifies_and_detects_broken_link(self):
        identity_receipt = signed("service_identity", identity_subject())
        identity = verified_identity(identity_receipt)
        first = signed("audit_event", audit_subject(identity, event_time=NOW))
        second = signed("audit_event", audit_subject(
            identity, previous=receipt_sha256(first), event_time=NOW + 1,
        ), issued_at=NOW + 1)
        result = verify_audit_chain(
            [first, second], trusted_public_keys=KEYS,
            identity_receipt=identity_receipt,
            expected_service_id="main-api", expected_commit_sha=COMMIT,
            expected_nonce=NONCE, now=NOW + 1,
        )
        self.assertEqual(len(result), 2)
        broken = copy.deepcopy(second)
        broken["body"]["subject"]["previous_receipt_sha256"] = "f" * 64
        broken["signature"] = base64.urlsafe_b64encode(
            PRIVATE.sign(canonical_json(broken["body"]))
        ).decode().rstrip("=")
        with self.assertRaisesRegex(ReceiptError, "audit_chain_broken"):
            verify_audit_chain(
                [first, broken], trusted_public_keys=KEYS,
                identity_receipt=identity_receipt,
                expected_service_id="main-api", expected_commit_sha=COMMIT,
                expected_nonce=NONCE, now=NOW + 1,
            )

    def test_receipt_lifetime_is_bounded(self):
        receipt = signed("service_identity", identity_subject(), ttl=901)
        with self.assertRaisesRegex(ReceiptError, "invalid_receipt_lifetime"):
            verified_identity(receipt)


if __name__ == "__main__":
    unittest.main()
