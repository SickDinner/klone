"""Trusted, externally stored checkpoint sequence contract.

This does NOT store the anchor or key. The caller must persist the latest
accepted anchor outside the protected SQLite database, atomically and with
rollback protection. In-memory or same-database anchors are insufficient.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json

from .research_checkpoint import LedgerCheckpoint


@dataclass(frozen=True)
class CheckpointAnchor:
    sequence: int
    checkpoint_digest: str
    previous_anchor_digest: str
    anchor_digest: str


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()


def _checkpoint_digest(checkpoint: LedgerCheckpoint) -> str:
    if not isinstance(checkpoint, LedgerCheckpoint) or checkpoint.format_version != 1:
        raise ValueError("Invalid checkpoint format")
    return _digest([checkpoint.format_version, checkpoint.row_count,
                    checkpoint.snapshot_sha256, checkpoint.signature])


def advance_anchor(
    *, checkpoint: LedgerCheckpoint, previous: CheckpointAnchor | None,
    expected_sequence: int,
) -> CheckpointAnchor:
    """Produce a candidate next anchor, without claiming durable persistence.

    Trusted caller MUST verify checkpoint HMAC against the actual database
    before invoking this function, then CAS-persist the returned anchor.
    """
    if type(expected_sequence) is not int or expected_sequence < 1:
        raise ValueError("Invalid checkpoint sequence")
    if previous is None:
        if expected_sequence != 1:
            raise ValueError("First checkpoint must have sequence one")
        prev_digest = "0" * 64
    else:
        if not isinstance(previous, CheckpointAnchor):
            raise ValueError("Invalid previous anchor")
        if expected_sequence != previous.sequence + 1:
            raise ValueError("Sequence must advance by exactly one")
        if previous.anchor_digest != _digest([
            previous.sequence, previous.checkpoint_digest,
            previous.previous_anchor_digest]):
            raise ValueError("Previous anchor integrity failure")
        prev_digest = previous.anchor_digest
    checkpoint_digest = _checkpoint_digest(checkpoint)
    anchor_digest = _digest([expected_sequence, checkpoint_digest, prev_digest])
    return CheckpointAnchor(expected_sequence, checkpoint_digest,
                            prev_digest, anchor_digest)


def check_anchored_checkpoint(
    *, checkpoint: LedgerCheckpoint, anchor: CheckpointAnchor,
    minimum_sequence: int,
) -> bool:
    """Compare to trusted external anchor; no database or key access."""
    if (not isinstance(anchor, CheckpointAnchor)
        or type(minimum_sequence) is not int or minimum_sequence < 1
        or type(anchor.sequence) is not int or anchor.sequence < minimum_sequence):
        return False
    try:
        checkpoint_digest = _checkpoint_digest(checkpoint)
        expected = _digest([anchor.sequence, anchor.checkpoint_digest,
                            anchor.previous_anchor_digest])
    except (ValueError, TypeError):
        return False
    return (
        hmac.compare_digest(checkpoint_digest, anchor.checkpoint_digest)
        and hmac.compare_digest(expected, anchor.anchor_digest)
    )
