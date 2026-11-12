"""Offline, deny-by-default outbound model request policy.

No network transport is provided by this module. It cannot enable external egress.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Literal

Zone = Literal["public_knowledge", "personal_knowledge", "sensitive_cognition", "restricted_bio"]
Decision = Literal["deny", "require_approval", "allow"]
KNOWN_ZONES = frozenset(("public_knowledge", "personal_knowledge", "sensitive_cognition", "restricted_bio"))


@dataclass(frozen=True)
class PayloadPart:
    kind: str
    classification: str
    content_sha256: str
    byte_length: int
    source_room_id: str

    def valid(self) -> bool:
        return (
            bool(self.kind.strip())
            and self.classification in KNOWN_ZONES
            and len(self.content_sha256) == 64
            and all(char in "0123456789abcdef" for char in self.content_sha256)
            and isinstance(self.byte_length, int)
            and not isinstance(self.byte_length, bool)
            and self.byte_length >= 0
            and bool(self.source_room_id.strip())
        )


@dataclass(frozen=True)
class EgressRequest:
    request_id: str
    room_id: str
    principal: str
    actor_role: str
    provider: str
    model: str
    purpose: str
    policy_version: str
    parts: tuple[PayloadPart, ...]
    serialized_payload_sha256: str


@dataclass(frozen=True)
class EgressDecision:
    decision: Decision
    reason_code: str
    manifest_sha256: str

    @property
    def permitted(self) -> bool:
        return self.decision == "allow"


def _manifest_hash(request: EgressRequest) -> str:
    manifest = {
        "request_id": request.request_id,
        "room_id": request.room_id,
        "principal": request.principal,
        "actor_role": request.actor_role,
        "provider": request.provider,
        "model": request.model,
        "purpose": request.purpose,
        "policy_version": request.policy_version,
        "serialized_payload_sha256": request.serialized_payload_sha256,
        "parts": [
            {
                "kind": part.kind,
                "classification": part.classification,
                "content_sha256": part.content_sha256,
                "byte_length": part.byte_length,
                "source_room_id": part.source_room_id,
            }
            for part in request.parts
        ],
    }
    return sha256(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def evaluate_egress(
    request: EgressRequest,
    *,
    allowlisted_destinations: frozenset[tuple[str, str]] = frozenset(),
    external_enabled: bool = False,
) -> EgressDecision:
    """Pure policy check. No grants or human approvals are issued here.

    The default configuration denies every external call. Even when enabled,
    only explicitly allowlisted public data from the same room can pass.
    """
    manifest_hash = _manifest_hash(request)

    def result(decision: Decision, code: str) -> EgressDecision:
        return EgressDecision(decision, code, manifest_hash)

    fields = (
        request.request_id, request.room_id, request.principal, request.actor_role,
        request.provider, request.model, request.purpose, request.policy_version,
    )
    if any(not isinstance(field, str) or not field.strip() for field in fields):
        return result("deny", "invalid_request")
    if len(request.serialized_payload_sha256) != 64 or any(
        char not in "0123456789abcdef" for char in request.serialized_payload_sha256
    ):
        return result("deny", "invalid_serialized_hash")
    if not request.parts or any(not isinstance(part, PayloadPart) or not part.valid() for part in request.parts):
        return result("deny", "invalid_manifest")
    if any(part.source_room_id != request.room_id for part in request.parts):
        return result("deny", "cross_room_source")
    if any(part.classification in ("sensitive_cognition", "restricted_bio") for part in request.parts):
        return result("deny", "sensitive_external_egress_denied")
    if any(part.classification == "personal_knowledge" for part in request.parts):
        return result("require_approval", "personal_data_requires_separate_approval")
    if not external_enabled:
        return result("deny", "external_transport_disabled")
    if (request.provider, request.model) not in allowlisted_destinations:
        return result("deny", "destination_not_allowlisted")
    return result("allow", "public_payload_allowed_by_explicit_policy")


def verify_serialized_payload(payload: bytes, expected_sha256: str) -> bool:
    """Recheck the final byte stream immediately before any transport call."""
    return sha256(payload).hexdigest() == expected_sha256
