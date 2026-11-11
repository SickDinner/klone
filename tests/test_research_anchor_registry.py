from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from klone.research_anchor_registry import SqliteAnchorRegistry, AnchorConflict
from klone.research_checkpoint import LedgerCheckpoint
from klone.research_checkpoint_anchor import advance_anchor


class AnchorRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.registry = SqliteAnchorRegistry(Path(self.temp.name) / "anchor.sqlite")
        self.checkpoint = LedgerCheckpoint(1, 2, "a" * 64, "b" * 64)

    def test_create_advance_and_reopen(self):
        self.assertIsNone(self.registry.read())
        first = advance_anchor(
            checkpoint=self.checkpoint, previous=None, expected_sequence=1)
        self.registry.compare_and_swap(expected=None, next_anchor=first)
        second = advance_anchor(
            checkpoint=self.checkpoint, previous=first, expected_sequence=2)
        self.registry.compare_and_swap(expected=first, next_anchor=second)
        self.assertEqual(self.registry.read(), second)
        self.assertEqual(SqliteAnchorRegistry(self.registry.path).read(), second)

    def test_stale_writer_rejected(self):
        first = advance_anchor(
            checkpoint=self.checkpoint, previous=None, expected_sequence=1)
        self.registry.compare_and_swap(expected=None, next_anchor=first)
        second = advance_anchor(
            checkpoint=self.checkpoint, previous=first, expected_sequence=2)
        with self.assertRaises(AnchorConflict):
            self.registry.compare_and_swap(expected=None, next_anchor=second)

    def test_skip_and_forgery_rejected(self):
        first = advance_anchor(
            checkpoint=self.checkpoint, previous=None, expected_sequence=1)
        with self.assertRaises(ValueError):
            self.registry.compare_and_swap(
                expected=None, next_anchor=replace(first, sequence=3))
        self.registry.compare_and_swap(expected=None, next_anchor=first)
        with self.assertRaises(ValueError):
            self.registry.compare_and_swap(
                expected=first, next_anchor=first)


if __name__ == "__main__":
    unittest.main()
