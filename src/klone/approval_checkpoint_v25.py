"""Detached Ed25519 checkpoints for KLONE v2.4 ingress audit (LAB ONLY).

This module does not publish/store anchors, issue approval, run IPC, or guard
signing keys. A trusted, separately isolated signer must supply a private key;
a verifier must independently obtain the pinned public key AND latest trusted
checkpoint digest from a rollback-resistant source outside the audit database.
"""
from __future__ import annotations

from dataclasses import dataclass
import base64
import binascii
from hashlib import sha256
import hmac
import json
import re
import sqlite3

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey,
)

from .approval_ingress_v24 import V24AuditLedger, AuditUnavailable

_DOMAIN = 'klone-approval-audit-checkpoint-v25-lab'
_GENESIS = '0' * 64
_HASH = re.compile(r'[0-9a-f]{64}\Z')
_SCOPE = re.compile(r'[a-z0-9][a-z0-9._-]{0,63}\Z')
_FIELDS = frozenset({'domain', 'version', 'scope_id', 'checkpoint_sequence',
                     'previous_checkpoint_sha256', 'audit_rows', 'screened_rows',
                     'seen_rows', 'tip_tag'})
_MAX_RECORD = 2048
_MAX_TRANSPORT = 4096


class CheckpointUnavailable(PermissionError):
    """The audit cannot be safely captured or checked."""


@dataclass(frozen=True)
class SignedApprovalCheckpoint:
    payload: bytes
    signature_hex: str


@dataclass(frozen=True)
class CheckpointCheck:
    accepted: bool
    reason: str
    checkpoint_sequence: int | None = None


def _canonical(value: dict) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('ascii')


def _strict_pairs(pairs):
    out = {}
    for name, value in pairs:
        if name in out:
            raise ValueError('duplicate_field')
        out[name] = value
    return out


def _validate_scope(scope_id: str) -> None:
    if type(scope_id) is not str or not _SCOPE.fullmatch(scope_id):
        raise ValueError('invalid_scope_id')


def _validate_digest(digest: str) -> None:
    if type(digest) is not str or not _HASH.fullmatch(digest):
        raise ValueError('invalid_checkpoint_digest')


def _fields(payload: bytes) -> dict:
    if type(payload) is not bytes or not 1 <= len(payload) <= _MAX_RECORD:
        raise ValueError('invalid_checkpoint_payload')
    try:
        fields = json.loads(payload.decode('ascii'), object_pairs_hook=_strict_pairs,
                            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        if type(fields) is not dict or set(fields) != _FIELDS or _canonical(fields) != payload:
            raise ValueError('noncanonical_checkpoint')
        if fields['domain'] != _DOMAIN or type(fields['version']) is not int or fields['version'] != 1:
            raise ValueError('invalid_checkpoint_domain')
        _validate_scope(fields['scope_id'])
        if (type(fields['checkpoint_sequence']) is not int
                or not 1 <= fields['checkpoint_sequence'] <= 2**63-1):
            raise ValueError('invalid_checkpoint_sequence')
        _validate_digest(fields['previous_checkpoint_sha256'])
        _validate_digest(fields['tip_tag'])
        for key in ('audit_rows', 'screened_rows', 'seen_rows'):
            if type(fields[key]) is not int or not 0 <= fields[key] <= 2**63-1:
                raise ValueError('invalid_checkpoint_count')
        if (fields['screened_rows'] != fields['seen_rows']
                or fields['screened_rows'] > fields['audit_rows']
                or (fields['audit_rows'] == 0 and fields['tip_tag'] != _GENESIS)):
            raise ValueError('inconsistent_checkpoint_counts')
        return fields
    except (ValueError, UnicodeError, TypeError, KeyError, OverflowError, RecursionError) as exc:
        raise ValueError('invalid_checkpoint_payload') from exc


def _snapshot(ledger: V24AuditLedger) -> tuple[int, int, int, str]:
    """Return a consistent read snapshot, checking both log and replay ledger.

    This runs one BEGIN read transaction, and refuses to inherit a caller's
    transaction. Existing v2.4 audit rows are never changed by this module.
    """
    if not isinstance(ledger, V24AuditLedger):
        raise CheckpointUnavailable('trusted_audit_ledger_required')
    conn = ledger.conn
    if conn.in_transaction:
        raise CheckpointUnavailable('audit_connection_not_idle')
    begun = False
    try:
        conn.execute('BEGIN')
        begun = True
        audit_rows, tag = ledger._verify_open_transaction()
        screened = conn.execute(
            "SELECT COUNT(*) FROM approval_v24_ingress_audit WHERE decision='screened'"
        ).fetchone()[0]
        seen = conn.execute(
            'SELECT COUNT(*) FROM approval_v24_ingress_seen'
        ).fetchone()[0]
        if (type(audit_rows) is not int or type(screened) is not int
                or type(seen) is not int or screened != seen
                or not 0 <= screened <= audit_rows or type(tag) is not str
                or not _HASH.fullmatch(tag)):
            raise CheckpointUnavailable('audit_replay_count_mismatch')
        return audit_rows, screened, seen, tag
    except (AuditUnavailable, sqlite3.Error, TypeError, ValueError, OverflowError,
            AttributeError) as exc:
        raise CheckpointUnavailable('audit_snapshot_unavailable') from exc
    finally:
        if begun:
            conn.rollback()


def checkpoint_digest(checkpoint: SignedApprovalCheckpoint) -> str:
    """Digest for independent external persistence; never derived from DB."""
    if not isinstance(checkpoint, SignedApprovalCheckpoint):
        raise ValueError('invalid_checkpoint')
    _fields(checkpoint.payload)
    # Ed25519 is exactly 64 signature bytes, represented by 128 lowercase hex chars.
    if (type(checkpoint.signature_hex) is not str
            or not re.fullmatch(r'[0-9a-f]{128}\Z', checkpoint.signature_hex)):
        raise ValueError('invalid_checkpoint_signature')
    return sha256(b'klone-v25-checkpoint\x00' + checkpoint.payload +
                  bytes.fromhex(checkpoint.signature_hex)).hexdigest()


def create_signed_checkpoint(*, ledger: V24AuditLedger, signing_key: Ed25519PrivateKey,
                             scope_id: str, checkpoint_sequence: int,
                             previous_checkpoint_sha256: str) -> SignedApprovalCheckpoint:
    """Construct a candidate checkpoint; DOES NOT anchor/publish it.

    Caller must authenticate and enforce sequence/parent against independent
    state before signing and externally persist the resulting digest by CAS.
    """
    if not isinstance(signing_key, Ed25519PrivateKey):
        raise ValueError('external_signing_key_required')
    _validate_scope(scope_id)
    if type(checkpoint_sequence) is not int or not 1 <= checkpoint_sequence <= 2**63-1:
        raise ValueError('invalid_checkpoint_sequence')
    _validate_digest(previous_checkpoint_sha256)
    if checkpoint_sequence == 1 and previous_checkpoint_sha256 != _GENESIS:
        raise ValueError('first_checkpoint_parent_required')
    if checkpoint_sequence > 1 and previous_checkpoint_sha256 == _GENESIS:
        raise ValueError('parent_checkpoint_required')
    audit_rows, screened, seen, tip_tag = _snapshot(ledger)
    payload = _canonical({'domain': _DOMAIN, 'version': 1, 'scope_id': scope_id,
        'checkpoint_sequence': checkpoint_sequence,
        'previous_checkpoint_sha256': previous_checkpoint_sha256,
        'audit_rows': audit_rows, 'screened_rows': screened,
        'seen_rows': seen, 'tip_tag': tip_tag})
    signature = signing_key.sign(payload)
    return SignedApprovalCheckpoint(payload, signature.hex())


def verify_signed_checkpoint(*, ledger: V24AuditLedger,
                            checkpoint: SignedApprovalCheckpoint,
                            trusted_public_key: Ed25519PublicKey,
                            trusted_checkpoint_sha256: str,
                            expected_scope_id: str,
                            minimum_checkpoint_sequence: int,
                            trusted_previous_sha256: str | None = None) -> CheckpointCheck:
    """Deny unless independent trust AND current database agree exactly.

    `trusted_checkpoint_sha256` MUST be obtained outside the SQLite DB and
    not from the untrusted artifact being checked. A signed old checkpoint is
    still a rollback unless a trusted monotonic anchor selects the latest one.
    """
    if not isinstance(trusted_public_key, Ed25519PublicKey):
        return CheckpointCheck(False, 'missing_trusted_public_key')
    try:
        _validate_scope(expected_scope_id)
        _validate_digest(trusted_checkpoint_sha256)
        if trusted_previous_sha256 is not None:
            _validate_digest(trusted_previous_sha256)
        if (type(minimum_checkpoint_sequence) is not int
                or minimum_checkpoint_sequence < 1):
            raise ValueError('invalid_minimum_sequence')
        fields = _fields(checkpoint.payload)
        if fields['scope_id'] != expected_scope_id:
            return CheckpointCheck(False, 'scope_mismatch')
        if fields['checkpoint_sequence'] < minimum_checkpoint_sequence:
            return CheckpointCheck(False, 'checkpoint_rollback')
        if (trusted_previous_sha256 is not None and
                not hmac.compare_digest(fields['previous_checkpoint_sha256'], trusted_previous_sha256)):
            return CheckpointCheck(False, 'parent_checkpoint_mismatch')
        digest = checkpoint_digest(checkpoint)
        if not hmac.compare_digest(digest, trusted_checkpoint_sha256):
            return CheckpointCheck(False, 'external_anchor_mismatch')
        trusted_public_key.verify(bytes.fromhex(checkpoint.signature_hex), checkpoint.payload)
        audit_rows, screened, seen, tag = _snapshot(ledger)
        if (audit_rows != fields['audit_rows'] or screened != fields['screened_rows']
                or seen != fields['seen_rows'] or
                not hmac.compare_digest(tag, fields['tip_tag'])):
            return CheckpointCheck(False, 'audit_snapshot_mismatch')
        return CheckpointCheck(True, 'checkpoint_verified_against_external_anchor',
                               fields['checkpoint_sequence'])
    except InvalidSignature:
        return CheckpointCheck(False, 'invalid_checkpoint_signature')
    except (ValueError, TypeError, AttributeError, OverflowError, binascii.Error):
        return CheckpointCheck(False, 'invalid_checkpoint_input')
    except (CheckpointUnavailable, sqlite3.Error):
        return CheckpointCheck(False, 'audit_unavailable')


def export_checkpoint(checkpoint: SignedApprovalCheckpoint) -> bytes:
    """Bounded, public, deterministic transport; contains NO private key."""
    checkpoint_digest(checkpoint)
    return _canonical({'payload_b64': base64.b64encode(checkpoint.payload).decode('ascii'),
                       'signature_hex': checkpoint.signature_hex})


def import_checkpoint(raw: bytes) -> SignedApprovalCheckpoint:
    if type(raw) is not bytes or not 1 <= len(raw) <= _MAX_TRANSPORT:
        raise ValueError('invalid_checkpoint_transport')
    try:
        obj = json.loads(raw.decode('ascii'), object_pairs_hook=_strict_pairs)
        if (type(obj) is not dict or set(obj) != {'payload_b64', 'signature_hex'}
                or type(obj['payload_b64']) is not str
                or _canonical(obj) != raw):
            raise ValueError('invalid_checkpoint_transport')
        payload = base64.b64decode(obj['payload_b64'], validate=True)
        checkpoint = SignedApprovalCheckpoint(payload, obj['signature_hex'])
        checkpoint_digest(checkpoint)
        return checkpoint
    except (UnicodeError, TypeError, KeyError, ValueError, OverflowError,
            binascii.Error, RecursionError) as exc:
        raise ValueError('invalid_checkpoint_transport') from exc
