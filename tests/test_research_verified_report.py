import unittest

from klone.genomics_hypotheses import EvidenceItem, Hypothesis
from klone.research_dossier import build_dossier
from klone.research_source_manifest import manifest_public_source
from klone.research_verified_report import publish_verified_dossier_report


class VerifiedReportTests(unittest.TestCase):
    def setUp(self):
        self.dossier = build_dossier(
            version=1, hypotheses=(Hypothesis("h", "Claim"),),
            evidence=(EvidenceItem("e", "archive:1", "h", "uncertain",
                                   "unknown", "Unverified claim", "archive"),))
        self.manifest = manifest_public_source(source_id="archive:1", content=b"source")

    def test_publish_with_matching_bytes(self):
        report = publish_verified_dossier_report(
            dossier=self.dossier, manifests={"archive:1": self.manifest},
            source_bytes={"archive:1": b"source"})
        self.assertEqual(report.verified_source_ids, ("archive:1",))
        self.assertIn("archive:1", report.markdown)

    def test_missing_or_changed_bytes_fail_closed(self):
        for source in ({}, {"archive:1": b"changed"}):
            with self.subTest(source=source), self.assertRaises(ValueError):
                publish_verified_dossier_report(
                    dossier=self.dossier, manifests={"archive:1": self.manifest},
                    source_bytes=source)


if __name__ == "__main__":
    unittest.main()
