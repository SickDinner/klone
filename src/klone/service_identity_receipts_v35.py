"""Verify signed local service identity and audit receipts (v3.5 LAB).

This module verifies claims made by an explicitly trusted observer. A valid
signature authenticates the observer's claim; it does not independently
inspect /proc, prove that the process is still running, or grant authority.
It has no network, filesystem, process-control, database, or key-generation IO.

Private signing keys belong in an out-of-band trusted observer, never in KLONE
source, a receipt, a test fixture shipped to users, or a production database.
"""
from __future__ import annotations

import base64
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import hmac
import json
import re
import uuid

DOMAIN = "klone-service-audit-receipt-v1"
MAX_RECEIPT_BYTES = 65_536
MAX_TTL_SECONDS = 900
MAX_FUTURE_SKEW_SECONDS = 30
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_SHA1 = re.compile(r"[0-9a-f]{40}\Z")
_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_KEY_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")
_RECEIPT_ID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z"
)

_ENVELOPE_KEYS = frozenset(("body", "signature"))
_BODY_KEYS = frozenset((
    "schema_version", "domain", "receipt_type", "receipt_id", "issuer",
    "key_id", "issued_at", "expires_at", "nonce", "subject",
))
_IDENTITY_KEYS = frozenset((
    "service_id", "pid", "process_start_time_ns", "owner_uid",
    "executable_sha256", "command_sha256", "listen_host", "listen_port",
    "application_commit_sha", "observer_id",
))
_AUDIT_KEYS = frozenset((
    "event_id", "actor_service_id", "actor_identity_receipt_sha256",
    "action", "resource_type", "resource_id", "outcome", "event_time",
    "request_sha256", "previous_receipt_sha256",
))


class ReceiptError(ValueError):
    """Stable fail-closed receipt validation error."""


@dataclass(frozen=True)
class TrustedObserverKey:
    """Out-of-band binding between one key ID, issuer name, and public key."""

    issuer: str
    public_key: object


@dataclass(frozen=True)
class VerifiedServiceIdentity:
    """Authenticated observer claims; not a live process handle or authority."""

    service_id: str
    pid: int
    process_start_time_ns: int
    owner_uid: int
    executable_sha256: str
    command_sha256: str
    listen_host: str
    listen_port: int
    application_commit_sha: str
    observer_id: str
    issuer: str
    key_id: str
    issued_at: int
    expires_at: int
    receipt_sha256: str
    live_process_rechecked: bool = False


def canonical_json(value: object) -> bytes:
    """Stable ASCII JSON used for signatures and receipt hashes."""
    try:
        encoded = json.dumps(value, ensure_ascii=True, sort_keys=True,
                             separators=(",", ":"), allow_nan=False).encode("ascii")
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise ReceiptError("invalid_json_value") from exc
    if len(encoded) > MAX_RECEIPT_BYTES:
        raise ReceiptError("receipt_too_large")
    return encoded


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ReceiptError("duplicate_json_key")
        result[key] = value
    return result


def parse_receipt_json(raw: str | bytes) -> dict:
    """Parse a receipt without accepting duplicate keys or non-finite values."""
    if type(raw) not in (str, bytes):
        raise ReceiptError("invalid_receipt_json")
    try:
        if len(raw) > MAX_RECEIPT_BYTES:
            raise ReceiptError("receipt_too_large")
        value = json.loads(
            raw, object_pairs_hook=_unique_pairs,
            parse_constant=lambda _value: (_ for _ in ()).throw(
                ReceiptError("invalid_json_constant")),
        )
    except ReceiptError:
        raise
    except (ValueError, UnicodeError, RecursionError, TypeError) as exc:
        raise ReceiptError("invalid_receipt_json") from exc
    if type(value) is not dict:
        raise ReceiptError("invalid_receipt")
    return value


def receipt_sha256(receipt: Mapping) -> str:
    """Return the canonical envelope digest (integrity aid, not a signature)."""
    return hashlib.sha256(canonical_json(receipt)).hexdigest()


def _token(value, code: str) -> str:
    if type(value) is not str or not _TOKEN.fullmatch(value):
        raise ReceiptError(code)
    return value


def _int(value, *, minimum: int, code: str) -> int:
    if type(value) is not int or value < minimum:
        raise ReceiptError(code)
    return value


def _hex(value, pattern, code: str) -> str:
    if type(value) is not str or not pattern.fullmatch(value):
        raise ReceiptError(code)
    return value


def _uuid(value, code: str) -> str:
    if type(value) is not str or not _RECEIPT_ID.fullmatch(value):
        raise ReceiptError(code)
    try:
        parsed = uuid.UUID(value)
    except ValueError as exc:
        raise ReceiptError(code) from exc
    if str(parsed) != value:
        raise ReceiptError(code)
    return value


def _public_key(value):
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError as exc:
        raise ReceiptError("cryptography_dependency_missing") from exc
    if isinstance(value, Ed25519PublicKey):
        return value
    if type(value) is bytes and len(value) == 32:
        try:
            return Ed25519PublicKey.from_public_bytes(value)
        except ValueError as exc:
            raise ReceiptError("invalid_trusted_public_key") from exc
    raise ReceiptError("invalid_trusted_public_key")


def _verify_signature(body: dict, signature: str, trusted_public_keys: Mapping[str, object]):
    if not isinstance(trusted_public_keys, Mapping):
        raise ReceiptError("invalid_trust_store")
    key_id = body["key_id"]
    if key_id not in trusted_public_keys:
        raise ReceiptError("untrusted_key_id")
    trusted = trusted_public_keys[key_id]
    if not isinstance(trusted, TrustedObserverKey):
        raise ReceiptError("invalid_trusted_key_entry")
    if type(trusted.issuer) is not str or not _TOKEN.fullmatch(trusted.issuer):
        raise ReceiptError("invalid_trusted_issuer")
    if body["issuer"] != trusted.issuer:
        raise ReceiptError("untrusted_issuer")
    if type(signature) is not str or not re.fullmatch(r"[A-Za-z0-9_-]{86}", signature):
        raise ReceiptError("invalid_signature_encoding")
    try:
        signature_bytes = base64.b64decode(
            signature + "==", altchars=b"-_", validate=True,
        )
    except (ValueError, base64.binascii.Error) as exc:
        raise ReceiptError("invalid_signature_encoding") from exc
    if len(signature_bytes) != 64 or base64.urlsafe_b64encode(
            signature_bytes).decode("ascii").rstrip("=") != signature:
        raise ReceiptError("invalid_signature_encoding")
    try:
        _public_key(trusted.public_key).verify(
            signature_bytes, canonical_json(body),
        )
    except ReceiptError:
        raise
    except Exception as exc:
        # cryptography's InvalidSignature must not leak implementation details.
        from cryptography.exceptions import InvalidSignature
        if isinstance(exc, InvalidSignature):
            raise ReceiptError("signature_invalid") from exc
        raise ReceiptError("signature_verification_failed") from exc


def _validate_body(receipt: Mapping, *, trusted_public_keys: Mapping[str, object],
                   expected_nonce: str, now: int, max_age: int) -> dict:
    if type(receipt) is not dict or set(receipt) != _ENVELOPE_KEYS:
        raise ReceiptError("invalid_receipt")
    body = receipt["body"]
    if type(body) is not dict or set(body) != _BODY_KEYS:
        raise ReceiptError("invalid_receipt_body")
    if (type(body["schema_version"]) is not int or body["schema_version"] != 1
            or body["domain"] != DOMAIN):
        raise ReceiptError("unsupported_receipt_schema")
    if body["receipt_type"] not in ("service_identity", "audit_event"):
        raise ReceiptError("invalid_receipt_type")
    _uuid(body["receipt_id"], "invalid_receipt_id")
    _token(body["issuer"], "invalid_issuer")
    if type(body["key_id"]) is not str or not _KEY_ID.fullmatch(body["key_id"]):
        raise ReceiptError("invalid_key_id")
    issued_at = _int(body["issued_at"], minimum=0, code="invalid_issued_at")
    expires_at = _int(body["expires_at"], minimum=1, code="invalid_expires_at")
    if expires_at <= issued_at or expires_at - issued_at > MAX_TTL_SECONDS:
        raise ReceiptError("invalid_receipt_lifetime")
    if type(now) is not int or now < 0 or type(max_age) is not int or not 1 <= max_age <= MAX_TTL_SECONDS:
        raise ReceiptError("invalid_verification_clock")
    if issued_at > now + MAX_FUTURE_SKEW_SECONDS:
        raise ReceiptError("receipt_from_future")
    if now > expires_at:
        raise ReceiptError("receipt_expired")
    if now - issued_at > max_age:
        raise ReceiptError("receipt_too_old")
    nonce = body["nonce"]
    if type(nonce) is not str or not re.fullmatch(r"[A-Za-z0-9._:-]{16,128}", nonce):
        raise ReceiptError("invalid_nonce")
    if type(expected_nonce) is not str or not re.fullmatch(
            r"[A-Za-z0-9._:-]{16,128}", expected_nonce):
        raise ReceiptError("invalid_expected_nonce")
    if not hmac.compare_digest(nonce, expected_nonce):
        raise ReceiptError("nonce_mismatch")
    subject = body["subject"]
    if type(subject) is not dict:
        raise ReceiptError("invalid_receipt_subject")
    _verify_signature(body, receipt["signature"], trusted_public_keys)
    return body


def _validate_identity_subject(subject: dict) -> dict:
    if set(subject) != _IDENTITY_KEYS:
        raise ReceiptError("invalid_service_identity_subject")
    result = dict(subject)
    _token(result["service_id"], "invalid_service_id")
    _int(result["pid"], minimum=1, code="invalid_process_id")
    _int(result["process_start_time_ns"], minimum=1, code="invalid_process_start_time")
    _int(result["owner_uid"], minimum=0, code="invalid_owner_uid")
    _hex(result["executable_sha256"], _SHA256, "invalid_executable_digest")
    _hex(result["command_sha256"], _SHA256, "invalid_command_digest")
    if result["listen_host"] not in ("127.0.0.1", "::1"):
        raise ReceiptError("non_loopback_service_identity")
    port = _int(result["listen_port"], minimum=1, code="invalid_listen_port")
    if port > 65535:
        raise ReceiptError("invalid_listen_port")
    _hex(result["application_commit_sha"], _SHA1, "invalid_application_commit")
    _token(result["observer_id"], "invalid_observer_id")
    return result


def verify_service_identity_receipt(
    receipt: Mapping, *, trusted_public_keys: Mapping[str, object],
    expected_nonce: str, expected_service_id: str, expected_commit_sha: str,
    now: int, max_age: int = 300,
) -> VerifiedServiceIdentity:
    """Verify one signed observer claim and bind it to caller expectations.

    This authenticates the signed observer statement only. The caller must use
    a fresh nonce, configure the trust keys out-of-band, and separately decide
    whether the observer is trusted to inspect local process state.
    """
    body = _validate_body(receipt, trusted_public_keys=trusted_public_keys,
                          expected_nonce=expected_nonce, now=now, max_age=max_age)
    if body["receipt_type"] != "service_identity":
        raise ReceiptError("wrong_receipt_type")
    subject = _validate_identity_subject(body["subject"])
    if subject["service_id"] != _token(expected_service_id, "invalid_expected_service_id"):
        raise ReceiptError("service_id_mismatch")
    if subject["application_commit_sha"] != _hex(
            expected_commit_sha, _SHA1, "invalid_expected_commit"):
        raise ReceiptError("application_commit_mismatch")
    return VerifiedServiceIdentity(
        service_id=subject["service_id"], pid=subject["pid"],
        process_start_time_ns=subject["process_start_time_ns"],
        owner_uid=subject["owner_uid"], executable_sha256=subject["executable_sha256"],
        command_sha256=subject["command_sha256"], listen_host=subject["listen_host"],
        listen_port=subject["listen_port"],
        application_commit_sha=subject["application_commit_sha"],
        observer_id=subject["observer_id"], issuer=body["issuer"],
        key_id=body["key_id"], issued_at=body["issued_at"],
        expires_at=body["expires_at"], receipt_sha256=receipt_sha256(receipt),
    )


def verify_audit_receipt(
    receipt: Mapping, *, trusted_public_keys: Mapping[str, object],
    identity_receipt: Mapping, expected_service_id: str,
    expected_commit_sha: str, expected_nonce: str, now: int, max_age: int = 300,
) -> dict:
    """Verify an audit event and reverify its signed actor identity receipt.

    Do not accept a caller-constructed VerifiedServiceIdentity instance as
    proof: Python objects are forgeable. The signed receipt and trust store are
    checked again on every public audit verification call.
    """
    identity = verify_service_identity_receipt(
        identity_receipt, trusted_public_keys=trusted_public_keys,
        expected_nonce=expected_nonce, expected_service_id=expected_service_id,
        expected_commit_sha=expected_commit_sha, now=now, max_age=max_age,
    )
    return _verify_audit_event(
        receipt, trusted_public_keys=trusted_public_keys, identity=identity,
        expected_nonce=expected_nonce, now=now, max_age=max_age,
    )


def _verify_audit_event(
    receipt: Mapping, *, trusted_public_keys: Mapping[str, object],
    identity: VerifiedServiceIdentity, expected_nonce: str, now: int,
    max_age: int,
) -> dict:
    """Internal checker; identity must come from verify_service_identity_receipt."""
    if type(now) is not int or now > identity.expires_at:
        raise ReceiptError("service_identity_expired")
    body = _validate_body(receipt, trusted_public_keys=trusted_public_keys,
                          expected_nonce=expected_nonce, now=now, max_age=max_age)
    if body["receipt_type"] != "audit_event":
        raise ReceiptError("wrong_receipt_type")
    subject = body["subject"]
    if set(subject) != _AUDIT_KEYS:
        raise ReceiptError("invalid_audit_subject")
    _uuid(subject["event_id"], "invalid_event_id")
    actor = _token(subject["actor_service_id"], "invalid_actor_service_id")
    if actor != identity.service_id:
        raise ReceiptError("audit_actor_mismatch")
    if _hex(subject["actor_identity_receipt_sha256"], _SHA256,
            "invalid_identity_receipt_digest") != identity.receipt_sha256:
        raise ReceiptError("audit_identity_receipt_mismatch")
    action = _token(subject["action"], "invalid_audit_action")
    resource_type = _token(subject["resource_type"], "invalid_resource_type")
    resource_id = _token(subject["resource_id"], "invalid_resource_id")
    outcome = subject["outcome"]
    if outcome not in ("allowed", "denied", "failed"):
        raise ReceiptError("invalid_audit_outcome")
    event_time = _int(subject["event_time"], minimum=0, code="invalid_event_time")
    if abs(event_time - body["issued_at"]) > MAX_FUTURE_SKEW_SECONDS:
        raise ReceiptError("audit_time_mismatch")
    request_hash = _hex(subject["request_sha256"], _SHA256, "invalid_request_digest")
    previous_hash = subject["previous_receipt_sha256"]
    if previous_hash != "0" * 64:
        _hex(previous_hash, _SHA256, "invalid_previous_receipt_digest")
    return {
        "event_id": subject["event_id"], "actor_service_id": actor,
        "actor_identity_receipt_sha256": identity.receipt_sha256,
        "action": action, "resource_type": resource_type,
        "resource_id": resource_id, "outcome": outcome,
        "event_time": event_time, "request_sha256": request_hash,
        "previous_receipt_sha256": previous_hash,
        "receipt_sha256": receipt_sha256(receipt),
        "issuer": body["issuer"], "key_id": body["key_id"],
    }


def verify_audit_chain(
    receipts: Sequence[Mapping], *, trusted_public_keys: Mapping[str, object],
    identity_receipt: Mapping, expected_service_id: str,
    expected_commit_sha: str, expected_nonce: str, now: int, max_age: int = 300,
) -> list[dict]:
    """Verify a bounded ordered chain with unique IDs and signed links."""
    if type(receipts) not in (list, tuple) or not 1 <= len(receipts) <= 1000:
        raise ReceiptError("invalid_audit_chain_length")
    identity = verify_service_identity_receipt(
        identity_receipt, trusted_public_keys=trusted_public_keys,
        expected_nonce=expected_nonce, expected_service_id=expected_service_id,
        expected_commit_sha=expected_commit_sha, now=now, max_age=max_age,
    )
    verified = []
    previous = "0" * 64
    last_event_time = -1
    seen_event_ids = set()
    seen_receipt_ids = set()
    for receipt in receipts:
        event = _verify_audit_event(
            receipt, trusted_public_keys=trusted_public_keys, identity=identity,
            expected_nonce=expected_nonce, now=now, max_age=max_age,
        )
        receipt_id = receipt["body"]["receipt_id"]
        if event["event_id"] in seen_event_ids:
            raise ReceiptError("duplicate_audit_event_id")
        if receipt_id in seen_receipt_ids:
            raise ReceiptError("duplicate_audit_receipt_id")
        if event["previous_receipt_sha256"] != previous:
            raise ReceiptError("audit_chain_broken")
        if event["event_time"] < last_event_time:
            raise ReceiptError("audit_chain_time_order")
        seen_event_ids.add(event["event_id"])
        seen_receipt_ids.add(receipt_id)
        previous = event["receipt_sha256"]
        last_event_time = event["event_time"]
        verified.append(event)
    return verified

