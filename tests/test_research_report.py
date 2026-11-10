from __future__ import annotations

import unittest

from klone.hypervisor_safe_pipeline import SafeReadResult
from klone.research_report import build_research_report


class ResearchReportTests(unittest.TestCase):
    def result(self, **changes):
        payload = {"question": "DNA chronology", "source_count": 1,
                   "results": [{"source_id": "a", "title": "Chronology",
                                "reference": "archive:a", "excerpt": "Dated evidence."}]}
        payload.update(changes)
        return SafeReadResult("trace-1", "public-room", "research.search", payload)

    def test_report_has_trace_and_citations(self):
        report = build_research_report(self.result())
        self.assertIn("Dated evidence.", report.markdown)
        self.assertIn("trace-1", report.markdown)
        self.assertEqual(report.citations, ("archive:a",))

    def test_no_sources_no_invented_conclusion(self):
        report = build_research_report(self.result(results=[], source_count=0))
        self.assertIn("ei löytynyt", report.markdown)
        self.assertEqual(report.citations, ())

    def test_invalid_citation_rejected(self):
        with self.assertRaises(ValueError):
            build_research_report(self.result(results=[{"title": "missing"}]))

    def test_count_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            build_research_report(self.result(source_count=3))


if __name__ == "__main__":
    unittest.main()
