import tempfile
from pathlib import Path
from unittest import TestCase

from klone.genomics_hypotheses import EvidenceItem, Hypothesis
from klone.hypervisor_runtime import HypervisorRuntime
from klone.research_memory import ResearchMemory
from klone.research_report import ResearchReport
from klone.research_proposals import prepare_claim_proposal
from klone.research_review_bundle import prepare_review_bundle
from klone.research_signed_grants import issue_research_grant
from klone.research_source_manifest import manifest_public_source
from klone.research_strict_publication import publish_strict_public_claim
from klone.research_atomic_ledger import AtomicResearchLedger


class StrictPublicationTests(TestCase):
    def test_valid_then_stale_report_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "shared.sqlite"
            memory = ResearchMemory(path)
            report = ResearchReport("trace", "public-room", "Research",
                                    "# Research", ("source:1",))
            memory.save(report)
            proposal = prepare_claim_proposal(
                trace_id="trace", report_version=1, claim_id="claim",
                statement="Claim", source_refs=("source:1",))
            hypotheses = (Hypothesis("h", "Claim"),)
            evidence = (EvidenceItem("e", "source:1", "h", "supports",
                                     "medium", "Evidence", "archive"),)
            key = b"k" * 32
            def grant(nonce):
                return issue_research_grant(
                    principal="reviewer", resource_id="claim",
                    report_version=1, policy_version=3, expires_at=200,
                    nonce=nonce, key=key)
            args = dict(
                database_path=path, proposal=proposal,
                bundle=prepare_review_bundle(
                    proposal=proposal, hypotheses=hypotheses, evidence=evidence),
                hypotheses=hypotheses, evidence=evidence,
                manifests={"source:1": manifest_public_source(
                    source_id="source:1", content=b"source")},
                source_bytes={"source:1": b"source"},
                principal="reviewer", actor_role="owner", policy_version=3,
                now=100, key=key, decision_reason="Review",
                authenticate=lambda principal, role: True,
                authorize_commit=lambda principal, claim, role: True,
                transaction_policy=lambda db, principal, claim, version: None,
                runtime=HypervisorRuntime())
            receipt = publish_strict_public_claim(**dict(
                args, grant=grant("unique-nonce-123456")))
            self.assertTrue(AtomicResearchLedger(path).verify(receipt.proposal_id))
            memory.save(report)
            with self.assertRaises(PermissionError):
                publish_strict_public_claim(**dict(
                    args, grant=grant("unique-nonce-234567")))
