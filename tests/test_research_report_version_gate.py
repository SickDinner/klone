import unittest

from klone.research_memory import StoredResearchReport
from klone.research_proposals import prepare_claim_proposal
from klone.research_report_version_gate import verify_current_public_report


class ReportVersionGateTests(unittest.TestCase):
    def setUp(self):
        self.proposal = prepare_claim_proposal(
            trace_id="trace", report_version=2, claim_id="claim",
            statement="Claim", source_refs=("archive:1",))
        self.report = StoredResearchReport(
            "trace", 2, "public-room", "Research", "# Research",
            ("archive:1",), "digest", "2026-01-01T00:00:00Z")

    def test_latest_version_and_citations(self):
        self.assertEqual(verify_current_public_report(
            proposal=self.proposal,
            read_report=lambda trace, version: self.report), self.report)

    def test_stale_version_rejected(self):
        newer = StoredResearchReport(
            "trace", 3, "public-room", "Research", "# Research",
            ("archive:1",), "digest", "2026-01-01T00:00:00Z")
        with self.assertRaises(ValueError):
            verify_current_public_report(
                proposal=self.proposal,
                read_report=lambda trace, version: newer if version is None else self.report)

    def test_absent_citation_rejected(self):
        missing = StoredResearchReport(
            "trace", 2, "public-room", "Research", "# Research",
            (), "digest", "2026-01-01T00:00:00Z")
        with self.assertRaises(ValueError):
            verify_current_public_report(
                proposal=self.proposal,
                read_report=lambda trace, version: missing)

    def test_inconsistent_reads_rejected(self):
        with self.assertRaises(ValueError):
            verify_current_public_report(
                proposal=self.proposal,
                read_report=lambda trace, version: self.report if version is None else None)


if __name__ == "__main__":
    unittest.main()
