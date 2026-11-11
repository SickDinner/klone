import unittest

from klone.genomics_hypotheses import EvidenceItem, Hypothesis
from klone.research_proposals import prepare_claim_proposal
from klone.research_review_bundle import prepare_review_bundle
from klone.research_source_manifest import manifest_public_source
from klone.research_publication_preflight import preflight_publication


class PublicationPreflightTests(unittest.TestCase):
    def setUp(self):
        self.hypotheses = (Hypothesis("h", "Claim"),)
        self.evidence = (EvidenceItem("e", "archive:1", "h", "supports",
                                      "medium", "Public citation", "archive"),)
        self.proposal = prepare_claim_proposal(
            trace_id="trace", report_version=1, claim_id="claim",
            statement="Claim", source_refs=("archive:1",))
        self.bundle = prepare_review_bundle(
            proposal=self.proposal, hypotheses=self.hypotheses,
            evidence=self.evidence)
        self.manifests = {"archive:1": manifest_public_source(
            source_id="archive:1", content=b"source")}

    def call(self, **overrides):
        args = dict(proposal=self.proposal, bundle=self.bundle,
                    hypotheses=self.hypotheses, evidence=self.evidence,
                    manifests=self.manifests,
                    source_bytes={"archive:1": b"source"})
        args.update(overrides)
        return preflight_publication(**args)

    def test_valid_bundle_and_source(self):
        self.assertEqual(self.call().verified_source_ids, ("archive:1",))

    def test_changed_bytes_fail_closed(self):
        with self.assertRaises(ValueError):
            self.call(source_bytes={"archive:1": b"altered"})

    def test_missing_evidence_reference_fails_closed(self):
        other = prepare_claim_proposal(
            trace_id="trace", report_version=1, claim_id="claim",
            statement="Claim", source_refs=("not-in-evidence",))
        bundle = prepare_review_bundle(
            proposal=other, hypotheses=self.hypotheses, evidence=self.evidence)
        with self.assertRaises(ValueError):
            self.call(proposal=other, bundle=bundle)

    def test_changed_review_bundle_fails_closed(self):
        with self.assertRaises(ValueError):
            self.call(evidence=())


if __name__ == "__main__":
    unittest.main()
