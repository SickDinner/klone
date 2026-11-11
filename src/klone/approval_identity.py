"""Server-side verification of short-lived approval actor assertions.

The signing secret must be injected from a trusted server secret store.
No endpoints, token minting or Constitution mutation are provided.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import hmac
import json

from .approval_access import VerifiedActor


@dataclass(frozen=True)
class SignedActorAssertion:
    payload: bytes
    signature_hex: str


def verify_actor_assertion(
    assertion: SignedActorAssertion, *, secret: bytes, now: datetime,
    max_age_seconds: int = 300,
) -> VerifiedActor:
    """Verify a trusted issuer's signed, time-bound actor context; fail closed."""
    if (not isinstance(assertion, SignedActorAssertion)
            or not isinstance(secret, bytes) or len(secret) < 32
            or not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None
            or not isinstance(max_age_seconds, int) or isinstance(max_age_seconds, bool)
            or not 0 < max_age_seconds <= 300
            or not isinstance(assertion.payload, bytes) or len(assertion.payload) > 2048
            or not isinstance(assertion.signature_hex, str) or len(assertion.signature_hex) != 64):
        raise PermissionError("invalid_actor_assertion")
    expected = hmac.new(secret, assertion.payload, sha256).hexdigest()
    if not hmac.compare_digest(expected, assertion.signature_hex):
        raise PermissionError("invalid_actor_signature")
    try:
        obj = json.loads(assertion.payload.decode("utf-8"))
        if not isinstance(obj, dict) or set(obj) != {"actor_id", "role", "room_id", "issued_at"}:
            raise ValueError("invalid_fields")
        if any(not isinstance(obj[key], str) or not obj[key].strip() or len(obj[key]) > 128
               for key in ("actor_id", "role", "room_id")):
            raise ValueError("invalid_actor")
        if not isinstance(obj["issued_at"], int) or isinstance(obj["issued_at"], bool):
            raise ValueError("invalid_time")
        age = int(now.timestamp()) - obj["issued_at"]
        if age < 0 or age > max_age_seconds:
            raise ValueError("expired")
        if obj["role"] not in {"owner", "supervisor"}:
            raise ValueError("invalid_role")
    except (ValueError, UnicodeDecodeError, TypeError, OverflowError) as error:
        raise PermissionError("invalid_actor_claims") from error
    return VerifiedActor(obj["actor_id"], obj["role"], obj["room_id"], True)
