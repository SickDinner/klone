from __future__ import annotations

from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3
import unittest

from klone.research_memory import ResearchMemory
from klone.research_report import ResearchReport


class ResearchMemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.memory = ResearchMemory(Path(self.tmp.name) / "reports.sqlite")
        self.report = ResearchReport("trace-a", "public-room", "Question",
                                     "# First report", ("local:note.md#sha256=abc",))

    def test_roundtrip_and_versions(self):
        first = self.memory.save(self.report)
        second = self.memory.save(ResearchReport("trace-a", "public-room",
                            "Question", "# Second report", self.report.citations))
        self.assertEqual((first.version, second.version), (1, 2))
        self.assertEqual(self.memory.read(trace_id="trace-a").markdown, "# Second report")
        self.assertEqual(self.memory.read(trace_id="trace-a", version=1).markdown,
                         "# First report")
        self.assertEqual(first.content_sha256,
                         self.memory.read(trace_id="trace-a", version=1).content_sha256)

    def test_missing_returns_none(self):
        self.assertIsNone(self.memory.read(trace_id="missing"))

    def test_nonpublic_fails_closed(self):
        with self.assertRaises(ValueError):
            self.memory.save(ResearchReport("t", "private-room", "Q", "secret", ()))

    def test_modified_report_is_detected(self):
        self.memory.save(self.report)
        with closing(sqlite3.connect(self.memory.database_path)) as conn:
            with conn:
                conn.execute("UPDATE research_report_versions SET markdown='tampered'")
        with self.assertRaisesRegex(ValueError, "integrity"):
            self.memory.read(trace_id="trace-a")


if __name__ == "__main__":
    unittest.main()
