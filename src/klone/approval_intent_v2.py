"""Lab-only, request-bound approvals layered over KLONE's atomic gateway.

Requires Evidence Approval Bridge v1.2 to be installed on the SAME SQLite
connection. Does not isolate an OS process, issue real user credentials, or
approve activation/publication. No endpoints or external effects.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import hmac
import json
import re
import sqlite3
from threading import RLock
from typing import Callable

_DOMAIN = "klone-draft-approval-intent-v2"
_FIELDS = frozenset((
    "domain", "action", "actor_id", "room_id", "proposal_id", "target_version",
    "patch_sha256", "reason_sha256", "nonce", "issued_at", "expires_at",
))
_ACTIONS = frozenset(("approve_draft", "revoke_draft"))
_NONCE = re.compile(r"[0-9a-f]{32,128}\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class SignedDraftIntent:
    payload: bytes
    signature_hex: str


def _encode(fields: dict) -> bytes:
    return json.dumps(fields, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def make_intent_payload(*, action: str, actor_id: str, room_id: str,
                        proposal_id: str, target_version: str, patch_sha256: str,
                        issued_at: int, nonce: str, ttl_seconds: int = 120,
                        reason: str = "") -> bytes:
    """Compose untrusted data for an EXTERNAL trusted issuer to review/sign.

    This helper does not authenticate actors or grant authorization.
    """
    if action not in _ACTIONS:
        raise ValueError("intent_action_denied")
    if any(type(s) is not str or not s or len(s) > 128 for s in
           (actor_id, room_id, proposal_id, target_version)):
        raise ValueError("invalid_intent_identity")
    if type(patch_sha256) is not str or not _HASH.fullmatch(patch_sha256):
        raise ValueError("invalid_patch_digest")
    if type(nonce) is not str or not _NONCE.fullmatch(nonce):
        raise ValueError("invalid_nonce")
    if type(issued_at) is not int or type(ttl_seconds) is not int or not 1 <= ttl_seconds <= 120:
        raise ValueError("invalid_intent_time")
    if type(reason) is not str or len(reason) > 256:
        raise ValueError("invalid_reason")
    if (action == "approve_draft" and reason) or (action == "revoke_draft" and not reason.strip()):
        raise ValueError("invalid_reason_scope")
    return _encode({
        "domain": _DOMAIN, "action": action, "actor_id": actor_id,
        "room_id": room_id, "proposal_id": proposal_id,
        "target_version": target_version, "patch_sha256": patch_sha256,
        "reason_sha256": sha256(reason.encode("utf-8")).hexdigest(),
        "nonce": nonce, "issued_at": issued_at,
        "expires_at": issued_at + ttl_seconds,
    })


def verify_intent(intent: SignedDraftIntent, *, secret: bytes, now: datetime,
                  action: str, actor_id: str, room_id: str, proposal_id: str,
                  target_version: str, patch_sha256: str, reason: str = "") -> str:
    """Validate one signed operation and return its replay fingerprint.

    The expected identity/action/target fields MUST come from a trusted host,
    verified actor and current SQLite proposal, not from the intent itself.
    """
    if (type(secret) is not bytes or len(secret) < 32 or
            type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None or
            not isinstance(intent, SignedDraftIntent) or
            type(intent.payload) is not bytes or not 1 <= len(intent.payload) <= 2048 or
            type(intent.signature_hex) is not str or not _HASH.fullmatch(intent.signature_hex)):
        raise PermissionError("invalid_intent_context")
    actual = hmac.new(secret, intent.payload, sha256).hexdigest()
    if not hmac.compare_digest(actual, intent.signature_hex):
        raise PermissionError("invalid_intent_signature")
    try:
        fields = json.loads(intent.payload.decode("utf-8"))
        if type(fields) is not dict or set(fields) != _FIELDS:
            raise ValueError("invalid_fields")
        if fields["domain"] != _DOMAIN or fields["action"] not in _ACTIONS:
            raise ValueError("invalid_domain")
        if any(type(fields[k]) is not str or not fields[k] or len(fields[k]) > 128
               for k in ("actor_id", "room_id", "proposal_id", "target_version")):
            raise ValueError("invalid_identity")
        if type(fields["nonce"]) is not str or not _NONCE.fullmatch(fields["nonce"]):
            raise ValueError("invalid_nonce")
        if any(type(fields[k]) is not str or not _HASH.fullmatch(fields[k])
               for k in ("patch_sha256", "reason_sha256")):
            raise ValueError("invalid_digest")
        start, end = fields["issued_at"], fields["expires_at"]
        if type(start) is not int or type(end) is not int or not 1 <= end-start <= 120:
            raise ValueError("invalid_expiry")
        if not start <= int(now.timestamp()) < end:
            raise ValueError("expired_or_future_intent")
        if (fields["action"] != action or fields["actor_id"] != actor_id or
                fields["room_id"] != room_id or fields["proposal_id"] != proposal_id or
                fields["target_version"] != target_version or
                fields["patch_sha256"] != patch_sha256 or
                fields["reason_sha256"] != sha256(reason.encode("utf-8")).hexdigest()):
            raise ValueError("intent_scope_mismatch")
    except (ValueError, KeyError, TypeError, UnicodeDecodeError, OverflowError) as exc:
        raise PermissionError("invalid_intent_claims") from exc
    return sha256(intent.payload + bytes.fromhex(intent.signature_hex)).hexdigest()


class BoundDraftApprovalService:
    """Single-connection lab facade; all DB writes share the gateway transaction.

    This is NOT an OS isolation boundary: any code with access to the writable
    DB, the gateway object or the Python process can bypass this facade.
    The trusted host must not expose those references to untrusted clients.
    """

    def __init__(self, *, gateway, intent_secret: bytes,
                 clock: Callable[[], datetime]):
        from .approval_atomic_gateway import AtomicApprovalGateway
        if not isinstance(gateway, AtomicApprovalGateway):
            raise TypeError("atomic_gateway_required")
        if type(intent_secret) is not bytes or len(intent_secret) < 32:
            raise ValueError("intent_secret_required")
        if not callable(clock):
            raise ValueError("trusted_clock_required")
        conn = gateway.connection
        if conn.isolation_level is not None or conn.in_transaction:
            raise ValueError("autocommit_idle_connection_required")
        required_triggers = {
            "evidence_guard_approve_v11", "evidence_guard_activation_v11",
            "evidence_guard_binding_immutable_v11",
        }
        found = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger'"
        )}
        if not required_triggers.issubset(found):
            raise ValueError("signed_evidence_bridge_v12_required")
        self._gateway = gateway
        self._intent_secret = intent_secret
        self._clock = clock
        self._lock = RLock()
        conn.execute("CREATE TABLE IF NOT EXISTS approval_v2_intent_replay ("
                     "fingerprint TEXT PRIMARY KEY)")

    def _run(self, *, proposal_id: str, operation: str, reason: str,
             key_id: str, actor_assertion, intent: SignedDraftIntent):
        with self._lock:
            now = self._clock()  # Trusted clock; caller does not choose now.
            if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
                raise PermissionError("trusted_clock_unavailable")

            def action(actor):
                if actor.role != "owner":
                    raise PermissionError("owner_required")
                journal = self._gateway.access.journal
                proposal = journal.get(proposal_id)
                if proposal is None:
                    raise PermissionError("unknown_proposal")
                fingerprint = verify_intent(
                    intent, secret=self._intent_secret, now=now,
                    action=operation, actor_id=actor.actor_id, room_id=proposal.room_id,
                    proposal_id=proposal_id, target_version=proposal.target_version,
                    patch_sha256=proposal.patch_sha256, reason=reason,
                )
                self._gateway.connection.execute(
                    "INSERT INTO approval_v2_intent_replay (fingerprint) VALUES (?)",
                    (fingerprint,),
                )
                if operation == "approve_draft":
                    return self._gateway.access.transition(
                        proposal_id, "approved", actor=actor, now=now,
                        current_target_version=proposal.target_version,
                        current_patch_sha256=proposal.patch_sha256,
                    )
                if operation == "revoke_draft":
                    return self._gateway.access.revoke(
                        proposal_id, actor=actor, now=now, reason=reason,
                    )
                raise PermissionError("operation_denied")

            # Existing gateway inserts actor replay marker and executes action
            # inside one BEGIN IMMEDIATE transaction; journal uses SAVEPOINTs.
            return self._gateway._run(key_id, actor_assertion, now, action)

    def approve_draft(self, proposal_id: str, *, key_id: str,
                      actor_assertion, intent: SignedDraftIntent):
        return self._run(proposal_id=proposal_id, operation="approve_draft", reason="",
                         key_id=key_id, actor_assertion=actor_assertion, intent=intent)

    def revoke_draft(self, proposal_id: str, *, reason: str, key_id: str,
                     actor_assertion, intent: SignedDraftIntent):
        if type(reason) is not str or not reason.strip() or len(reason) > 256:
            raise ValueError("revocation_reason_required")
        return self._run(proposal_id=proposal_id, operation="revoke_draft", reason=reason,
                         key_id=key_id, actor_assertion=actor_assertion, intent=intent)
