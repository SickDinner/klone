"""Offline key-rotation verifier for approval assertions.

Keys must be provisioned by a trusted operator. This module never issues
tokens, loads environment secrets or grants target mutation privileges.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .approval_access import VerifiedActor
from .approval_identity import SignedActorAssertion, verify_actor_assertion


@dataclass(frozen=True)
class VerificationKey:
    key_id: str
    secret: bytes
    not_before_epoch: int
    not_after_epoch: int


class ApprovalKeyring:
    def __init__(self, keys: tuple[VerificationKey, ...]):
        if not keys or len(keys) > 8:
            raise ValueError("invalid_keyring")
        ids = set()
        for key in keys:
            if (not isinstance(key, VerificationKey)
                    or not isinstance(key.key_id, str)
                    or not key.key_id or len(key.key_id) > 64
                    or not isinstance(key.secret, bytes) or len(key.secret) < 32
                    or not isinstance(key.not_before_epoch, int)
                    or isinstance(key.not_before_epoch, bool)
                    or not isinstance(key.not_after_epoch, int)
                    or isinstance(key.not_after_epoch, bool)
                    or key.not_before_epoch >= key.not_after_epoch
                    or key.key_id in ids):
                raise ValueError("invalid_keyring")
            ids.add(key.key_id)
        self._keys = {key.key_id: key for key in keys}

    def verify(
        self, key_id: str, assertion: SignedActorAssertion, *, now: datetime,
    ) -> VerifiedActor:
        if not isinstance(key_id, str):
            raise PermissionError("unknown_signing_key")
        key = self._keys.get(key_id)
        if key is None:
            raise PermissionError("unknown_signing_key")
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise PermissionError("invalid_verification_time")
        epoch = int(now.timestamp())
        if not key.not_before_epoch <= epoch < key.not_after_epoch:
            raise PermissionError("signing_key_inactive")
        return verify_actor_assertion(assertion, secret=key.secret, now=now)
