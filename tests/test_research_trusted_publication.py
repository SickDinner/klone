import tempfile
from pathlib import Path
import unittest

from klone.genomics_hypotheses import EvidenceItem, Hypothesis
from klone.hypervisor_runtime import HypervisorRuntime
from klone.research_proposals import prepare_claim_proposal
from klone.research_review_bundle import prepare_review_bundle
from klone.research_signed_grants import issue_research_grant
from klone.research_source_manifest import manifest_public_source
from klone.research_trusted_publication import publish_trusted_research_claim


class TrustedPublicationTests(unittest.TestCase):
    def test_denied_privileged_commit_never_creates_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.sqlite"
            hypotheses = (Hypothesis("h", "Claim"),)
            evidence = (EvidenceItem("e", "source:1", "h", "supports",
                                     "medium", "Evidence", "archive"),)
            proposal = prepare_claim_proposal(
                trace_id="trace", report_version=1, claim_id="claim",
                statement="Claim", source_refs=("source:1",))
            bundle = prepare_review_bundle(
                proposal=proposal, hypotheses=hypotheses, evidence=evidence)
            key = b"k" * 32
            grant = issue_research_grant(
                principal="reviewer", resource_id="claim", report_version=1,
                policy_version=1, expires_at=200,
                nonce="nonce-unique-123456", key=key)
            with self.assertRaises(PermissionError):
                publish_trusted_research_claim(
                    database_path=path, proposal=proposal, bundle=bundle,
                    hypotheses=hypotheses, evidence=evidence,
                    manifests={"source:1": manifest_public_source(
                        source_id="source:1", content=b"source")},
                    source_bytes={"source:1": b"source"}, grant=grant,
                    principal="reviewer", actor_role="owner", policy_version=1,
                    now=100, key=key, decision_reason="Review",
                    authenticate=lambda principal, role: True,
                    authorize_commit=lambda principal, resource, role: False,
                    runtime=HypervisorRuntime())
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
