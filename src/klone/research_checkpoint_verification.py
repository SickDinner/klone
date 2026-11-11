"""Fail-closed composition of signed snapshots and externally trusted anchors.

The trusted caller supplies the anchor and minimum sequence from independent
rollback-resistant storage. This module cannot authenticate that storage.
No writes, key storage or HTTP endpoints are exposed.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .research_checkpoint import LedgerCheckpoint, verify_checkpoint
from .research_checkpoint_anchor import (
    CheckpointAnchor, check_anchored_checkpoint,
)


@dataclass(frozen=True)
class CheckpointVerification:
    accepted: bool
    reason: str
    sequence: int | None


def verify_research_checkpoint(
    *, database_path: Path, checkpoint: LedgerCheckpoint,
    anchor: CheckpointAnchor, minimum_sequence: int, key: bytes,
) -> CheckpointVerification:
    """Require a valid snapshot HMAC AND exact trusted anchor match."""
    if type(minimum_sequence) is not int or minimum_sequence < 1:
        return CheckpointVerification(False, "invalid_minimum_sequence", None)
    if not isinstance(anchor, CheckpointAnchor):
        return CheckpointVerification(False, "missing_trusted_anchor", None)
    if not check_anchored_checkpoint(
        checkpoint=checkpoint, anchor=anchor,
        minimum_sequence=minimum_sequence,
    ):
        return CheckpointVerification(False, "anchor_mismatch", None)
    if not verify_checkpoint(
        database_path=database_path, checkpoint=checkpoint, key=key,
    ):
        return CheckpointVerification(False, "snapshot_mismatch", None)
    return CheckpointVerification(True, "verified_snapshot_and_anchor",
                                  anchor.sequence)
