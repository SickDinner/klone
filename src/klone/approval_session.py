"""Offline signed session binding for approval actor assertions.

This module verifies a trusted issuer's session context, but does not issue
sessions, authenticate humans, or expose network routes.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import hmac
import json

from .approval_access import VerifiedActor


@dataclass(frozen=True)
class SessionAssertion:
    payload: bytes
    signature_hex: str
    key_id: str


def verify_session_assertion(
    assertion: SessionAssertion, *, secret: bytes, now: datetime,
    expected_session_id: str, expected_audience: str = "klone-approval",
    max_age_seconds: int = 120,
) -> VerifiedActor:
    if (not isinstance(assertion, SessionAssertion)
            or not isinstance(secret, bytes) or len(secret) < 32
            or not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None
            or not isinstance(expected_session_id, str) or not expected_session_id.strip()
            or not isinstance(expected_audience, str) or not expected_audience.strip()
            or not isinstance(max_age_seconds, int) or isinstance(max_age_seconds, bool)
            or not 0 < max_age_seconds <= 120
            or not isinstance(assertion.payload, bytes) or len(assertion.payload) > 2048
            or not isinstance(assertion.signature_hex, str) or len(assertion.signature_hex) != 64
            or not isinstance(assertion.key_id, str) or not assertion.key_id\n            or len(assertion.key_id) > 64 or not assertion.key_id.isascii()):
        raise PermissionError("invalid_session_assertion")
    expected = hmac.new(
        secret, b"klone-approval-session-v1\x00" + assertion.key_id.encode()
        + b"\x00" + assertion.payload, sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, assertion.signature_hex):
        raise PermissionError("invalid_session_signature")
    try:
        claims = json.loads(assertion.payload.decode("utf-8"))
        if not isinstance(claims, dict) or set(claims) != {
            "actor_id", "role", "room_id", "session_id", "audience", "issued_at"
        }:
            raise ValueError("invalid_claims")
        for field in ("actor_id", "role", "room_id", "session_id", "audience"):
            value = claims[field]
            if not isinstance(value, str) or not value.strip() or len(value) > 128:
                raise ValueError("invalid_field")
        if (claims["session_id"] != expected_session_id
                or claims["audience"] != expected_audience
                or claims["role"] not in {"owner", "supervisor"}):
            raise ValueError("session_binding_mismatch")
        issued = claims["issued_at"]
        if not isinstance(issued, int) or isinstance(issued, bool):
            raise ValueError("invalid_issued_at")
        age = int(now.timestamp()) - issued
        if age < 0 or age > max_age_seconds:
            raise ValueError("session_assertion_expired")
    except (ValueError, UnicodeDecodeError, TypeError, OverflowError) as error:
        raise PermissionError("invalid_session_claims") from error
    return VerifiedActor(claims["actor_id"], claims["role"], claims["room_id"], True)
