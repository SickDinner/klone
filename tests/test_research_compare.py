from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from klone.research_compare import compare_research_versions
from klone.research_memory import ResearchMemory
from klone.research_report import ResearchReport


class ResearchComparisonTests(unittest.TestCase):
    def test_changed_report_and_citations(self):
        with TemporaryDirectory() as directory:
            memory = ResearchMemory(Path(directory) / "reports.sqlite")
            memory.save(ResearchReport("t", "public-room", "Q", "old", ("a", "b")))
            memory.save(ResearchReport("t", "public-room", "Q", "new", ("b", "c")))
            result = compare_research_versions(
                memory, trace_id="t", old_version=1, new_version=2)
            self.assertEqual(result.added_citations, ("c",))
            self.assertEqual(result.removed_citations, ("a",))
            self.assertIn("+new", result.unified_diff)
            self.assertFalse(result.unchanged)

    def test_identical_and_invalid_versions(self):
        with TemporaryDirectory() as directory:
            memory = ResearchMemory(Path(directory) / "reports.sqlite")
            report = ResearchReport("t", "public-room", "Q", "same", ())
            memory.save(report)
            memory.save(report)
            result = compare_research_versions(
                memory, trace_id="t", old_version=1, new_version=2)
            self.assertTrue(result.unchanged)
            with self.assertRaises(ValueError):
                compare_research_versions(
                    memory, trace_id="t", old_version=2, new_version=1)


if __name__ == "__main__":
    unittest.main()
