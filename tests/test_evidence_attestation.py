"""Attestation trust and signature verification tests."""
from __future__ import annotations

import unittest

from klone.evidence_attestation import canonical, message, sign, verify
import hashlib
import contextlib
import io
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from klone.evidence_attestation import _load, main, validate_packet


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
        self.assertTrue(result["witness_authenticated"])
        self.assertTrue(result["key_in_trust_map"])
        self.assertFalse(result["origin_authenticated"])
        self.assertFalse(result["device_identity_verified"])
        self.assertFalse(result["test_execution_authenticated"])
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

    def test_rehashed_packet_with_changed_commit_still_invalidates_signature(self):
        self.packet['commit'] = 'b' * 40
        self.packet['packet_sha256'] = hashlib.sha256(canonical({k:v for k,v in self.packet.items() if k != 'packet_sha256'})).hexdigest()
        self.signature['packet_sha256'] = self.packet['packet_sha256']
        self.assertEqual(verify(self.packet, self.signature, {'termux-device':self.public})['reason'], 'bad_signature')

    def test_different_domain_is_rejected(self):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        import base64
        payload = message(self.packet, 'termux-device').replace(b'ATTESTATION-V1', b'ATTESTATION-V2')
        self.signature['signature_b64'] = base64.b64encode(Ed25519PrivateKey.from_private_bytes(self.secret).sign(payload)).decode('ascii')
        self.assertEqual(verify(self.packet, self.signature, {'termux-device':self.public})['reason'], 'bad_signature')

    def test_oversized_or_invalid_signature_never_reaches_crypto(self):
        for value in ('A' * 1000000, '!' * 88, None):
            self.signature['signature_b64'] = value
            with patch('klone.evidence_attestation._crypto') as crypto:
                self.assertFalse(verify(self.packet, self.signature, {'termux-device':self.public})['signature_valid'])
                crypto.assert_not_called()

    def test_missing_crypto_backend_is_explicit_and_does_not_install(self):
        with patch('klone.evidence_attestation._crypto', side_effect=RuntimeError('missing')):
            result = verify(self.packet, self.signature, {'termux-device':self.public})
        self.assertEqual(result['reason'], 'crypto_unavailable')
        self.assertFalse(result['witness_authenticated'])

    def test_false_approval_claim_or_wrong_schema_rejected(self):
        for key,value in (('schema_version', True), ('deployment_approval', True), ('device_identity_verified', True)):
            modified = {**self.packet, key:value}
            self.assertFalse(verify(modified, self.signature, {'termux-device':self.public})['signature_valid'])

    def test_explicit_trust_map_cannot_be_replaced_by_embedded_key(self):
        self.signature['public_key'] = self.public
        self.assertFalse(verify(self.packet, self.signature, {})['signature_valid'])

    def test_verification_preserves_inputs_and_is_deterministic(self):
        trusted = {'termux-device':self.public}
        before = canonical([self.packet, self.signature, trusted])
        self.assertEqual(verify(self.packet, self.signature, trusted), verify(self.packet, self.signature, trusted))
        self.assertEqual(before, canonical([self.packet, self.signature, trusted]))

    def test_cli_verifies_without_writing_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inputs = [self.packet, self.signature, {'termux-device':self.public}]
            paths = [root / n for n in ('packet.json','signature.json','trusted.json')]
            for path,data in zip(paths, inputs):
                path.write_text(json.dumps(data))
            before = {p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in paths}
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main(['--packet',str(paths[0]),'--attestation',str(paths[1]),'--trusted-keys',str(paths[2])])
            self.assertEqual(code, 0)
            self.assertTrue(json.loads(output.getvalue())['witness_authenticated'])
            self.assertEqual(before, {p.name:(p.read_bytes(),p.stat().st_mtime_ns) for p in paths})


class AttestationIOTests(unittest.TestCase):
    def test_strict_bounded_json_and_symlink_handling(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'input.json'
            for raw in (b'{broken', b'{"x":1,"x":2}', b'{"x":NaN}', b'[]', b' ' * 131073):
                path.write_bytes(raw)
                with self.assertRaises(ValueError):
                    _load(path)
            path.write_text('{}')
            linked = path.with_name('link.json')
            try:
                linked.symlink_to(path)
            except OSError:
                self.skipTest('symlink creation not permitted')
            with self.assertRaises(ValueError):
                _load(linked)

    def test_malformed_input_cli_is_a_controlled_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'bad.json'
            path.write_text('null')
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                main(['--packet',str(path),'--attestation',str(path),'--trusted-keys',str(path)])
            self.assertEqual(error.exception.code, 2)

    def test_packet_bool_schema_and_missing_timestamp_rejected(self):
        p = packet()
        p['schema_version'] = True
        with self.assertRaises(ValueError):
            validate_packet(p)
        p = packet()
        del p['observed_at']
        self.assertFalse(verify(p, {}, {})['signature_valid'])


if __name__ == "__main__":
    unittest.main()
