"""Attestation trust and signature verification tests."""
from __future__ import annotations

import unittest

from klone.evidence_attestation import canonical, message, sign, verify
import hashlib


def packet():
    data = {
        "schema_version": 1, "kind": "klone-evidence-packet",
        "commit": "a" * 40, "observed_at": "2026-11-12T19:00:00Z",
        "device_identity_verified": False, "deployment_approval": False,
    }
    return {**data, "packet_sha256": hashlib.sha256(canonical(data)).hexdigest()}


class AttestationTests(unittest.TestCase):
    def setUp(self):
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
            from cryptography.hazmat.primitives import serialization
        except ImportError:
            self.skipTest("optional cryptography dependency not installed")
        self.secret = bytes(range(32))
        private = Ed25519PrivateKey.from_private_bytes(self.secret)
        self.public = private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw).hex()
        self.packet = packet()
        self.signature = sign(self.packet, "termux-device", self.secret)

    def test_valid_signature_is_not_deployment_approval(self):
        result = verify(self.packet, self.signature, {"termux-device": self.public})
        self.assertTrue(result["signature_valid"])
        self.assertTrue(result["origin_authenticated"])
        self.assertFalse(result["deployment_approval"])

    def test_untrusted_key_rejected(self):
        result = verify(self.packet, self.signature, {})
        self.assertEqual(result["reason"], "untrusted_witness")

    def test_wrong_public_key_rejected(self):
        result = verify(self.packet, self.signature, {"termux-device": "0" * 64})
        self.assertFalse(result["signature_valid"])

    def test_modified_commit_rejected(self):
        self.packet["commit"] = "b" * 40
        result = verify(self.packet, self.signature, {"termux-device": self.public})
        self.assertFalse(result["signature_valid"])

    def test_modified_signature_rejected(self):
        self.signature["signature_b64"] = "AA=="
        result = verify(self.packet, self.signature, {"termux-device": self.public})
        self.assertFalse(result["signature_valid"])

    def test_witness_id_is_bound_to_signature(self):
        self.signature["witness_id"] = "other"
        result = verify(self.packet, self.signature, {"other": self.public})
        self.assertFalse(result["signature_valid"])

    def test_domain_separation(self):
        self.assertIn(b"KLONE-EVIDENCE-ATTESTATION-V1", message(self.packet, "termux-device"))


if __name__ == "__main__":
    unittest.main()
