from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from klone.research_files import load_research_texts


class ResearchFileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "note.md").write_text("Ancient DNA evidence", encoding="utf-8")

    def load(self, paths, **kwargs):
        return load_research_texts(root=self.root, relative_paths=paths,
                                   room_id="public-room", **kwargs)

    def test_reads_explicit_text_with_digest(self):
        sources = self.load(["note.md"])
        self.assertEqual(len(sources), 1)
        self.assertIn("sha256=", sources[0].reference)
        self.assertEqual(sources[0].text, "Ancient DNA evidence")

    def test_rejects_traversal_and_absolute_paths(self):
        for path in ("../outside.md", str(self.root / "note.md")):
            with self.assertRaises(ValueError):
                self.load([path])

    def test_rejects_unsupported_extension(self):
        (self.root / "binary.exe").write_bytes(b"x")
        with self.assertRaises(ValueError):
            self.load(["binary.exe"])

    def test_rejects_oversized_file(self):
        with self.assertRaises(ValueError):
            self.load(["note.md"], max_file_bytes=4)

    def test_rejects_duplicate_paths(self):
        with self.assertRaises(ValueError):
            self.load(["note.md", "note.md"])

    def test_rejects_symlink(self):
        link = self.root / "alias.md"
        try:
            link.symlink_to(self.root / "note.md")
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks not supported on this host")
        with self.assertRaises(ValueError):
            self.load(["alias.md"])


if __name__ == "__main__":
    unittest.main()
