"""Security tests for the transaction-time policy hook."""
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from klone.genomics_hypotheses import EvidenceItem, Hypothesis
from klone.hypervisor_runtime import HypervisorRuntime
from klone.research_proposals import prepare_claim_proposal
from klone.research_review_bundle import prepare_review_bundle
from klone.research_signed_grants import issue_research_grant
from klone.research_source_manifest import manifest_public_source
from klone.research_trusted_publication import publish_trusted_research_claim


class TransactionPolicyTests(TestCase):
    def test_policy_guard_receives_trusted_scope(self):
        with tempfile.TemporaryDirectory() as temp:
            hypotheses = (Hypothesis("h", "Claim"),)
            evidence = (EvidenceItem("e", "source:1", "h", "supports",
                                     "medium", "Evidence", "archive"),)
            proposal = prepare_claim_proposal(
                trace_id="trace", report_version=1, claim_id="claim",
                statement="Claim", source_refs=("source:1",))
            key = b"k" * 32
            grant = issue_research_grant(
                principal="reviewer", resource_id="claim", report_version=1,
                policy_version=3, expires_at=200, nonce="unique-nonce-123456",
                key=key)
            checked = []
            def guard(connection, principal, claim_id, version):
                checked.append((principal, claim_id, version))
                raise PermissionError("Policy revoked")
            with self.assertRaises(PermissionError):
                publish_trusted_research_claim(
                    database_path=Path(temp) / "ledger.sqlite", proposal=proposal,
                    bundle=prepare_review_bundle(
                        proposal=proposal, hypotheses=hypotheses, evidence=evidence),
                    hypotheses=hypotheses, evidence=evidence,
                    manifests={"source:1": manifest_public_source(
                        source_id="source:1", content=b"source")},
                    source_bytes={"source:1": b"source"},
                    grant=grant, principal="reviewer", actor_role="owner",
                    policy_version=3, now=100, key=key,
                    decision_reason="Review",
                    authenticate=lambda principal, role: True,
                    authorize_commit=lambda principal, resource, role: True,
                    runtime=HypervisorRuntime(), commit_policy_guard=guard)
            self.assertEqual(checked, [("reviewer", "claim", 3)])
