from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3
import threading
import unittest

from klone.research_anchor_registry import AnchorConflict, SqliteAnchorRegistry
from klone.research_checkpoint import LedgerCheckpoint
from klone.research_checkpoint_anchor import advance_anchor


class AnchorIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.registry = SqliteAnchorRegistry(Path(self.temp.name) / "anchors.sqlite")
        cp = LedgerCheckpoint(1, 2, "a" * 64, "b" * 64)
        self.first = advance_anchor(checkpoint=cp, previous=None,
                                    expected_sequence=1)
        self.registry.compare_and_swap(expected=None, next_anchor=self.first)
        self.second = advance_anchor(checkpoint=cp, previous=self.first,
                                     expected_sequence=2)

    def test_tampered_stored_anchor_denied_on_read_and_cas(self):
        with closing(sqlite3.connect(self.registry.path)) as db, db:
            db.execute("UPDATE checkpoint_anchor SET anchor_digest=?", ("f" * 64,))
        with self.assertRaises(ValueError):
            self.registry.read()
        with self.assertRaises(ValueError):
            self.registry.compare_and_swap(
                expected=self.first, next_anchor=self.second)

    def test_two_competing_writers_only_one_succeeds(self):
        barrier = threading.Barrier(2)

        def write():
            barrier.wait(timeout=10)
            try:
                self.registry.compare_and_swap(
                    expected=self.first, next_anchor=self.second)
                return "accepted"
            except AnchorConflict:
                return "conflict"

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: write(), range(2)))
        self.assertCountEqual(results, ("accepted", "conflict"))
        self.assertEqual(self.registry.read(), self.second)


if __name__ == "__main__":
    unittest.main()
