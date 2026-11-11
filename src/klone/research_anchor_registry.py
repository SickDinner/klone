"""SQLite compare-and-swap anchor registry, isolated from research ledger.

The registry MUST be deployed on a separately protected storage boundary.
Using another SQLite file on the same writable filesystem does not provide
rollback resistance against an administrator. No key management or API here.
"""
from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3

from .research_checkpoint_anchor import CheckpointAnchor


class AnchorConflict(RuntimeError):
    """Expected prior anchor did not match stored state."""


class SqliteAnchorRegistry:
    def __init__(self, path: Path):
        self.path = Path(path)

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("""CREATE TABLE IF NOT EXISTS checkpoint_anchor (
            singleton INTEGER PRIMARY KEY CHECK(singleton=1),
            sequence INTEGER NOT NULL,
            checkpoint_digest TEXT NOT NULL,
            previous_anchor_digest TEXT NOT NULL,
            anchor_digest TEXT NOT NULL)""")
        return db

    def read(self) -> CheckpointAnchor | None:
        with closing(self._connect()) as db:
            row = db.execute("""SELECT sequence,checkpoint_digest,
                previous_anchor_digest,anchor_digest FROM checkpoint_anchor
                WHERE singleton=1""").fetchone()
        return CheckpointAnchor(*row) if row else None

    def compare_and_swap(
        self, *, expected: CheckpointAnchor | None, next_anchor: CheckpointAnchor,
    ) -> CheckpointAnchor:
        """Persist only a valid successor, under a serialized transaction."""
        if not isinstance(next_anchor, CheckpointAnchor):
            raise ValueError("Invalid next anchor")
        from .research_checkpoint_anchor import _digest
        if (type(next_anchor.sequence) is not int or next_anchor.sequence < 1
            or next_anchor.anchor_digest != _digest([
                next_anchor.sequence, next_anchor.checkpoint_digest,
                next_anchor.previous_anchor_digest])):
            raise ValueError("Invalid anchor integrity")
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("""SELECT sequence,checkpoint_digest,
                previous_anchor_digest,anchor_digest FROM checkpoint_anchor
                WHERE singleton=1""").fetchone()
            current = CheckpointAnchor(*row) if row else None
            if current != expected:
                raise AnchorConflict("Anchor changed concurrently")
            if current is None:
                if next_anchor.sequence != 1 or next_anchor.previous_anchor_digest != "0" * 64:
                    raise ValueError("First anchor must start at sequence one")
            elif (next_anchor.sequence != current.sequence + 1
                  or next_anchor.previous_anchor_digest != current.anchor_digest):
                raise ValueError("Anchor must advance exactly one step")
            db.execute("""INSERT INTO checkpoint_anchor VALUES (1,?,?,?,?)
                ON CONFLICT(singleton) DO UPDATE SET
                sequence=excluded.sequence,
                checkpoint_digest=excluded.checkpoint_digest,
                previous_anchor_digest=excluded.previous_anchor_digest,
                anchor_digest=excluded.anchor_digest""", (
                    next_anchor.sequence, next_anchor.checkpoint_digest,
                    next_anchor.previous_anchor_digest, next_anchor.anchor_digest))
        return next_anchor
