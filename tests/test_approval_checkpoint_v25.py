"""No production DB, network, OS credential mutation or persisted private keys."""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import secrets
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from klone.approval_checkpoint_v25 import (
    CheckpointUnavailable, SignedApprovalCheckpoint, checkpoint_digest,
    create_signed_checkpoint, export_checkpoint, import_checkpoint,
    verify_signed_checkpoint,
)
from klone.approval_ingress_v24 import V24AuditLedger


class ApprovalCheckpointV25Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='klone-v25-')
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'lab.sqlite'
        self.db = sqlite3.connect(self.path, isolation_level=None, timeout=3)
        # Close before temp cleanup, even on Windows.
        self.addCleanup(self.db.close)
        V24AuditLedger.initialize_lab_schema(self.db)
        self.ledger = V24AuditLedger(self.db, secret=secrets.token_bytes(32), clock=lambda: 1234)
        self.private = Ed25519PrivateKey.generate()
        self.public = self.private.public_key()
        self.scope = 'klone.lab.approval.ingress'

    def record(self, request_id='1'*32, reason=''):
        return self.ledger.record(peer_uid=2002,
            request_sha256='c'*64, reason=reason,
            request_id=request_id if not reason else None)

    def sign(self, sequence=1, previous='0'*64):
        return create_signed_checkpoint(
            ledger=self.ledger, signing_key=self.private, scope_id=self.scope,
            checkpoint_sequence=sequence, previous_checkpoint_sha256=previous)

    def check(self, checkpoint, **kwargs):
        return verify_signed_checkpoint(
            ledger=self.ledger, checkpoint=checkpoint,
            trusted_public_key=kwargs.get('key', self.public),
            trusted_checkpoint_sha256=kwargs.get('digest', checkpoint_digest(checkpoint)),
            expected_scope_id=kwargs.get('scope', self.scope),
            minimum_checkpoint_sequence=kwargs.get('minimum', 1),
            trusted_previous_sha256=kwargs.get('previous', None))

    def test_empty_genesis_capture(self):
        c = self.sign()
        self.assertTrue(self.check(c).accepted)
        self.assertFalse(self.db.in_transaction)

    def test_good_checkpoint_after_screening_and_denial(self):
        self.record()
        self.record('2'*32, reason='untrusted_peer')
        c = self.sign()
        self.assertTrue(self.check(c).accepted)
        body=json.loads(c.payload)
        self.assertEqual((body['audit_rows'], body['screened_rows'], body['seen_rows']), (2,1,1))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM approval_v24_ingress_audit').fetchone()[0],2)

    def test_capture_does_not_write_to_db(self):
        self.record()
        before='\n'.join(self.db.iterdump())
        self.sign()
        self.assertEqual(before,'\n'.join(self.db.iterdump()))

    def test_export_roundtrip_and_public_only(self):
        c=self.sign()
        data=export_checkpoint(c)
        self.assertEqual(import_checkpoint(data),c)
        self.assertTrue(self.check(import_checkpoint(data)).accepted)
        self.assertNotIn(b'private_key',data)

    def test_deterministic_transport(self):
        c=self.sign()
        self.assertEqual(export_checkpoint(c),export_checkpoint(c))

    def test_new_screening_detected_against_old_checkpoint(self):
        c=self.sign()
        self.record()
        self.assertEqual(self.check(c).reason,'audit_snapshot_mismatch')

    def test_new_denial_detected_against_old_checkpoint(self):
        c=self.sign()
        self.record('1'*32,reason='denied')
        self.assertEqual(self.check(c).reason,'audit_snapshot_mismatch')

    def test_tail_denial_deletion_detected_by_anchor(self):
        self.record()
        self.record('2'*32,reason='peer_not_allowlisted')
        c=self.sign()
        self.db.execute('DELETE FROM approval_v24_ingress_audit WHERE seq=2')
        self.assertTrue(self.ledger.verify_chain())  # Known v2.4 limitation.
        self.assertEqual(self.check(c).reason,'audit_snapshot_mismatch')

    def test_tail_screened_deletion_detected_by_seen_cross_check(self):
        self.record()
        self.record('2'*32)
        c=self.sign()
        self.db.execute('DELETE FROM approval_v24_ingress_audit WHERE seq=2')
        self.assertTrue(self.ledger.verify_chain())
        with self.assertRaisesRegex(CheckpointUnavailable,'audit_replay_count_mismatch'):
            self.sign(sequence=2,previous=checkpoint_digest(c))
        self.assertEqual(self.check(c).reason,'audit_unavailable')

    def test_tamper_audit_row_detected(self):
        self.record()
        c=self.sign()
        self.db.execute("UPDATE approval_v24_ingress_audit SET reason='wrong'")
        self.assertEqual(self.check(c).reason,'audit_unavailable')

    def test_old_signed_checkpoint_requires_new_external_digest(self):
        self.record()
        old=self.sign()
        self.record('2'*32,reason='denied')
        new=self.sign(2,checkpoint_digest(old))
        self.assertEqual(self.check(old,digest=checkpoint_digest(new)).reason,'external_anchor_mismatch')
        self.assertTrue(self.check(new,minimum=2,previous=checkpoint_digest(old)).accepted)

    def test_wrong_external_digest(self):
        c=self.sign()
        self.assertEqual(self.check(c,digest='a'*64).reason,'external_anchor_mismatch')

    def test_wrong_public_key(self):
        c=self.sign()
        key=Ed25519PrivateKey.generate().public_key()
        self.assertEqual(self.check(c,key=key).reason,'invalid_checkpoint_signature')

    def test_changed_signature_denied(self):
        c=self.sign()
        altered=replace(c,signature_hex='f'*128)
        self.assertEqual(self.check(altered,digest=checkpoint_digest(altered)).reason,'invalid_checkpoint_signature')

    def test_missing_public_key_denied(self):
        c=self.sign()
        self.assertEqual(self.check(c,key=None).reason,'missing_trusted_public_key')

    def test_scope_mismatch(self):
        c=self.sign()
        self.assertEqual(self.check(c,scope='some.other.scope').reason,'scope_mismatch')

    def test_minimum_sequence_enforces_rollback(self):
        c=self.sign()
        self.assertEqual(self.check(c,minimum=2).reason,'checkpoint_rollback')

    def test_parent_mismatch(self):
        c=self.sign()
        self.assertEqual(self.check(c,previous='f'*64).reason,'parent_checkpoint_mismatch')

    def test_wrong_parent_for_non_genesis_rejected(self):
        with self.assertRaisesRegex(ValueError,'parent_checkpoint_required'):
            self.sign(2,'0'*64)

    def test_wrong_genesis_parent_rejected(self):
        with self.assertRaisesRegex(ValueError,'first_checkpoint_parent_required'):
            self.sign(1,'f'*64)

    def test_bad_sequence_types_denied(self):
        for sequence in (0,-1, True, 1.1, 2**63):
            with self.subTest(sequence=sequence),self.assertRaises(ValueError):
                self.sign(sequence)

    def test_bad_scope_denied(self):
        for scope in ('', '../escape', 'SOMETHING', 'x'*100, None):
            with self.subTest(scope=scope),self.assertRaises(ValueError):
                create_signed_checkpoint(ledger=self.ledger,signing_key=self.private,
                    scope_id=scope,checkpoint_sequence=1,
                    previous_checkpoint_sha256='0'*64)

    def test_bad_signing_key_denied(self):
        with self.assertRaisesRegex(ValueError,'external_signing_key_required'):
            create_signed_checkpoint(ledger=self.ledger,signing_key=b'no',
                scope_id=self.scope,checkpoint_sequence=1,
                previous_checkpoint_sha256='0'*64)

    def test_import_rejects_duplicate_transport_fields(self):
        c=self.sign()
        data=export_checkpoint(c)
        obj=json.loads(data)
        bad=b'{' + b'"payload_b64":"' + obj['payload_b64'].encode() + b'",' + data[1:]
        with self.assertRaises(ValueError): import_checkpoint(bad)

    def test_import_rejects_modified_noncanonical_transport(self):
        data=export_checkpoint(self.sign())
        with self.assertRaises(ValueError): import_checkpoint(data+b'\n')

    def test_import_rejects_malformed_or_large(self):
        for data in (b'',b'x',b'[]',b'{}',b' '*4097,b'{"payload_b64":"!!!","signature_hex":"a"}'):
            with self.subTest(data=data[:25]),self.assertRaises(ValueError): import_checkpoint(data)

    def test_payload_wrong_signature_length_denied(self):
        c=self.sign()
        for malformed in ('0'*64, 'g'*128, '', 123):
            with self.subTest(sig=malformed),self.assertRaises(ValueError):
                checkpoint_digest(replace(c,signature_hex=malformed))

    def test_noncanonical_payload_rejected(self):
        c=self.sign()
        with self.assertRaises(ValueError):
            checkpoint_digest(replace(c,payload=c.payload+b' '))

    def test_duplicate_payload_keys_rejected(self):
        c=self.sign()
        bad=c.payload.replace(b'"version":1',b'"version":1,"version":1')
        with self.assertRaises(ValueError): checkpoint_digest(replace(c,payload=bad))

    def test_type_confusion_bool_version_rejected(self):
        c=self.sign()
        payload=c.payload.replace(b'"version":1',b'"version":true')
        with self.assertRaises(ValueError): checkpoint_digest(replace(c,payload=payload))

    def test_intentional_no_db_write_interface(self):
        import klone.approval_checkpoint_v25 as mod
        for key in ('approve','revoke','publish','activate','listen','serve','anchor_to_github'):
            self.assertFalse(hasattr(mod,key))

    def test_fails_closed_if_database_closed(self):
        c=self.sign()
        self.db.close()
        self.assertFalse(self.check(c).accepted)

    def test_transaction_in_progress_rejected(self):
        c=self.sign()
        self.db.execute('BEGIN')
        try:
            with self.assertRaisesRegex(CheckpointUnavailable,'not_idle'): self.sign()
            self.assertEqual(self.check(c).reason,'audit_unavailable')
        finally: self.db.rollback()

    def test_replay_table_discrepancy_denied(self):
        self.record()
        c=self.sign()
        self.db.execute('DELETE FROM approval_v24_ingress_seen')
        with self.assertRaises(CheckpointUnavailable): self.sign()
        self.assertEqual(self.check(c).reason,'audit_unavailable')

    def test_no_cryptographic_key_export(self):
        self.record()
        c=self.sign()
        data=export_checkpoint(c)
        self.assertLess(len(data),4096)
        self.assertEqual(self.check(c).reason,'checkpoint_verified_against_external_anchor')

    def test_capture_isolation_from_uncommitted_transactions(self):
        self.db.execute('BEGIN')
        try:
            self.db.execute('INSERT INTO approval_v24_ingress_seen (request_id) VALUES (?)',('f'*32,))
            with self.assertRaises(CheckpointUnavailable): self.sign()
        finally:
            self.db.rollback()
        self.assertTrue(self.check(self.sign()).accepted)

    def test_crypto_signature_size(self):
        c=self.sign()
        self.assertEqual(len(bytes.fromhex(c.signature_hex)),64)

    def test_scope_binds_even_if_payload_resigned_elsewhere(self):
        c=self.sign()
        body=json.loads(c.payload)
        body['scope_id']='another.lab'
        import klone.approval_checkpoint_v25 as mod
        modified=mod._canonical(body)
        signed=SignedApprovalCheckpoint(modified,self.private.sign(modified).hex())
        self.assertEqual(self.check(signed).reason,'scope_mismatch')

    def test_unsupported_invalid_trusted_digest_denied(self):
        c=self.sign()
        for digest in ('','f'*20,None,123):
            with self.subTest(digest=digest):
                self.assertFalse(self.check(c,digest=digest).accepted)


if __name__ == '__main__':
    unittest.main()
