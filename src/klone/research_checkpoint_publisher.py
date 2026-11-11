"""Trusted-service checkpoint publication, not an HTTP endpoint.

The caller must control the HMAC key and the anchor registry independently
of the research ledger. This implementation cannot guarantee cross-database
atomicity or rollback resistance of local SQLite files.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .research_anchor_registry import SqliteAnchorRegistry
from .research_atomic_ledger import AtomicResearchLedger
from .research_checkpoint import make_checkpoint, verify_checkpoint, LedgerCheckpoint
from .research_checkpoint_anchor import (
    advance_anchor, CheckpointAnchor, check_anchored_checkpoint,
)


@dataclass(frozen=True)
class PublishedCheckpoint:
    checkpoint: LedgerCheckpoint
    anchor: CheckpointAnchor


def publish_checkpoint(
    *, ledger_path: Path, registry: SqliteAnchorRegistry, key: bytes,
) -> PublishedCheckpoint:
    """Sign a ledger snapshot and CAS-publish its next anchor.

    A concurrent ledger write between snapshot and registry CAS may make the
    checkpoint immediately stale; readers must verify against live ledger.
    """
    problems = AtomicResearchLedger(ledger_path).reconcile()
    if problems:
        raise ValueError("Cannot publish inconsistent research ledger: "
                         + ", ".join(problems))
    previous = registry.read()
    checkpoint = make_checkpoint(database_path=ledger_path, key=key)
    if not verify_checkpoint(
        database_path=ledger_path, checkpoint=checkpoint, key=key,
    ):
        raise RuntimeError("Ledger changed during checkpoint verification")
    next_anchor = advance_anchor(
        checkpoint=checkpoint, previous=previous,
        expected_sequence=1 if previous is None else previous.sequence + 1,
    )
    registry.compare_and_swap(expected=previous, next_anchor=next_anchor)
    return PublishedCheckpoint(checkpoint, next_anchor)


def verify_published_checkpoint(
    *, ledger_path: Path, registry: SqliteAnchorRegistry,
    publication: PublishedCheckpoint, key: bytes,
) -> bool:
    """Require current trusted registry anchor and current ledger snapshot."""
    if not isinstance(publication, PublishedCheckpoint):
        return False
    current = registry.read()
    if current is None or current != publication.anchor:
        return False
    if not check_anchored_checkpoint(
        checkpoint=publication.checkpoint, anchor=current,
        minimum_sequence=current.sequence,
    ):
        return False
    return verify_checkpoint(
        database_path=ledger_path, checkpoint=publication.checkpoint, key=key,
    )
