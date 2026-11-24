"""v2.9 replayable read-only dossier tests; real hypervisor in GitHub CI."""
import copy
import itertools
import json
import unittest

from klone.evidence_lineage_v26 import EvidenceLineageNode
from klone.council72_portfolio_v26 import ReviewCandidate, plan_council72_review
from klone.cognition_metabolism_v28 import (
    ProcessSnapshot, ProviderTokenUsage, TaskResourceReceipt,
)
from klone.proof_carrying_cognition_v29 import (
    ReviewProofRequest, build_review_proof, verify_review_proof,
)


def evidence(i, **changes):
    data = {"node_id": f"n{i}", "claim_key": "claim1", "domain": "research",
            "source_group": f"g{i}", "content_sha256": f"{i:064x}",
            "stance": "supports", "room_id": "public-room", "classification": "public"}
    data.update(changes)
    return EvidenceLineageNode(**data)


def candidate(i=1, **changes):
    values = {"task_id": f"task{i}", "claim_key": "claim1", "domain": "research",
              "ring": 1, "seat": i, "priority": 100, "estimated_tokens": 100}
    values.update(changes)
    return ReviewCandidate(**values)


def request(**changes):
    data = dict(task_id="task1", claim_key="claim1", room_id="public-room",
                classification_level="public", actor_role="evaluator", trace_id="trace1")
    data.update(changes)
    return ReviewProofRequest(**data)


def receipt(tasks=None, *, usage=None, outcome="completed", end_ns=130,
            start_ns=100, plan=None, ring=1, seat=1):
    tasks = tasks or [candidate()]
    plan = plan or plan_council72_review([evidence(1), evidence(2), evidence(3)], tasks)
    return TaskResourceReceipt(
        task_id="task1", ring=ring, seat=seat, plan_sha256=plan["plan_sha256"],
        start=ProcessSnapshot(pid=123, monotonic_ns=start_ns, process_cpu_ns=10, current_rss_bytes=2048),
        end=ProcessSnapshot(pid=123, monotonic_ns=end_ns, process_cpu_ns=20, current_rss_bytes=3072),
        provider_usage=usage or ProviderTokenUsage(10, 20), outcome=outcome,
    )


class ReviewProofV29Tests(unittest.TestCase):
    def setUp(self):
        self.nodes = [evidence(1), evidence(2), evidence(3)]
        self.tasks = [candidate()]
        self.request = request()
        self.receipts = [receipt()]

    def build(self, **kwargs):
        return build_review_proof(kwargs.pop("nodes", self.nodes), kwargs.pop("tasks", self.tasks),
                                  kwargs.pop("receipts", self.receipts),
                                  kwargs.pop("request", self.request), **kwargs)

    def test_complete_packet_is_still_unverified(self):
        p = self.build()
        self.assertEqual(p["review_status"], "unverified_packet_ready_for_manual_review")
        self.assertEqual(p["review_holds"], [])
        self.assertFalse(p["approval_granted"])
        self.assertFalse(p["hypervisor_execution_authorized"])
        self.assertFalse(p["content_digests_authenticated"])
        self.assertFalse(p["usage_receipts_authenticated"])
        self.assertTrue(p["human_review_required"])

    def test_canonical_replay_succeeds_without_claimed_anchor(self):
        p = self.build()
        v = verify_review_proof(p, self.nodes, self.tasks, self.receipts, self.request)
        self.assertTrue(v["replay_matches"])
        self.assertFalse(v["matches_supplied_digest"])
        self.assertFalse(v["external_anchor_origin_authenticated"])

    def test_supplied_hash_match_does_not_authenticate_origin(self):
        p = self.build()
        v = verify_review_proof(p, self.nodes, self.tasks, self.receipts, self.request,
                                expected_external_sha256=p["report_sha256"])
        self.assertTrue(v["matches_supplied_digest"])
        self.assertFalse(v["external_anchor_origin_authenticated"])
        self.assertFalse(v["approval_granted"])

    def test_wrong_supplied_hash_rejected(self):
        p = self.build()
        self.assertFalse(verify_review_proof(p, self.nodes, self.tasks, self.receipts,
                      self.request, expected_external_sha256="f"*64)["matches_supplied_digest"])

    def test_bad_external_hash_rejected(self):
        for bad in ("ABC", 7, True, "F"*64):
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, "invalid_supplied_external_digest"):
                verify_review_proof(self.build(), self.nodes, self.tasks, self.receipts,
                                    self.request, expected_external_sha256=bad)

    def test_modification_of_report_caught(self):
        p = self.build()
        p["review_holds"].append("fake")
        self.assertFalse(verify_review_proof(p, self.nodes, self.tasks, self.receipts,
                         self.request)["replay_matches"])

    def test_reshashed_forged_report_caught_by_replay(self):
        p = self.build()
        p["approval_granted"] = True
        self.assertFalse(verify_review_proof(p, self.nodes, self.tasks, self.receipts,
                         self.request)["replay_matches"])

    def test_modified_evidence_digest_caught(self):
        p = self.build()
        altered = [evidence(1, content_sha256="a"*64), *self.nodes[1:]]
        self.assertFalse(verify_review_proof(p, altered, self.tasks, self.receipts,
                         self.request)["replay_matches"])

    def test_source_permutation_is_stable(self):
        p = self.build()
        self.assertEqual(p, self.build(nodes=list(reversed(self.nodes))))

    def test_task_permutation_is_stable(self):
        t = [candidate(), candidate(2, ring=2, seat=1, priority=80)]
        plan = plan_council72_review(self.nodes, t)
        r = [receipt(plan=plan)]
        self.assertEqual(self.build(tasks=t, receipts=r),
                         self.build(tasks=list(reversed(t)), receipts=r))

    def test_receipt_permutation_is_stable(self):
        t = [candidate(), candidate(2, ring=2, seat=1)]
        plan = plan_council72_review(self.nodes, t)
        a = receipt(plan=plan)
        b = TaskResourceReceipt(task_id="task2", ring=2, seat=1, plan_sha256=plan["plan_sha256"],
             start=ProcessSnapshot(pid=456, monotonic_ns=100, process_cpu_ns=10, current_rss_bytes=None),
             end=ProcessSnapshot(pid=456, monotonic_ns=130, process_cpu_ns=20, current_rss_bytes=None),
             provider_usage=ProviderTokenUsage(10, 10), outcome="completed")
        self.assertEqual(self.build(tasks=t, receipts=[a,b]), self.build(tasks=t, receipts=[b,a]))

    def test_only_two_sources_is_fragile(self):
        nodes = self.nodes[:2]
        plan = plan_council72_review(nodes, self.tasks)
        r = [receipt(plan=plan)]
        p = self.build(nodes=nodes, receipts=r)
        self.assertIn("single_group_failure_changes_candidate", p["review_holds"])

    def test_unknown_claim_blocks_evidence(self):
        nodes = [evidence(1, stance="unknown"), evidence(2), evidence(3)]
        plan = plan_council72_review(nodes, self.tasks)
        p = self.build(nodes=nodes, receipts=[])
        self.assertIn("evidence_not_candidate", p["review_holds"])
        self.assertIn("telemetry_needs_review", p["review_holds"])

    def test_conflicting_claim_blocks(self):
        nodes = [evidence(1), evidence(2), evidence(3, stance="contradicts")]
        p = self.build(nodes=nodes, receipts=[])
        self.assertIn("evidence_not_candidate", p["review_holds"])

    def test_no_receipts_blocks(self):
        p = self.build(receipts=[])
        self.assertEqual(p["resource_review_status"], "insufficient_telemetry")
        self.assertIn("telemetry_needs_review", p["review_holds"])

    def test_unknown_provider_usage_blocks(self):
        p = self.build(receipts=[receipt(usage=ProviderTokenUsage(None, None))])
        self.assertIn("telemetry_needs_review", p["review_holds"])

    def test_failed_receipt_blocks(self):
        p = self.build(receipts=[receipt(outcome="failed")])
        self.assertIn("telemetry_needs_review", p["review_holds"])

    def test_task_estimate_exceeded_blocks(self):
        p = self.build(receipts=[receipt(usage=ProviderTokenUsage(100, 20))])
        self.assertIn("telemetry_needs_review", p["review_holds"])

    def test_global_budget_exceeded_blocks(self):
        plan = plan_council72_review(self.nodes, self.tasks, max_total_tokens=100)
        p = self.build(receipts=[receipt(plan=plan, usage=ProviderTokenUsage(60, 50))],
                       max_total_tokens=100)
        self.assertIn("telemetry_needs_review", p["review_holds"])

    def test_queue_budget_denied_blocks(self):
        p = self.build(receipts=[], max_total_tokens=50)
        self.assertIn("task_not_queued", p["review_holds"])

    def test_undercovered_withdrawals_blocks(self):
        nodes = [evidence(i) for i in range(1, 5)]
        plan = plan_council72_review(nodes, self.tasks)
        p = self.build(nodes=nodes, receipts=[receipt(plan=plan)], max_source_groups=2)
        self.assertIn("counterfactual_coverage_incomplete", p["review_holds"])

    def test_non_public_scope_never_released(self):
        nodes = [evidence(1, room_id="sealed-room", classification="intimate"),
                 evidence(2, room_id="sealed-room", classification="intimate"),
                 evidence(3, room_id="sealed-room", classification="intimate")]
        with self.assertRaisesRegex(ValueError, "nonpublic_evidence_requires_governed_pipeline"):
            self.build(nodes=nodes, receipts=[],
                       request=request(room_id="sealed-room", classification_level="intimate"))

    def test_mixed_rooms_are_rejected_before_output(self):
        nodes = [evidence(1), evidence(2),
                 evidence(3, room_id="sealed-room", classification="intimate")]
        with self.assertRaisesRegex(ValueError, "nonpublic_evidence_requires_governed_pipeline"):
            self.build(nodes=nodes, receipts=[])

    def test_false_public_claim_scope_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "nonpublic_evidence_requires_governed_pipeline"):
            self.build(request=request(classification_level="personal"))

    def test_non_public_claim_keys_never_emitted(self):
        nodes = [evidence(1, claim_key="personal-secret-id", room_id="restricted-room", classification="personal")]
        with self.assertRaisesRegex(ValueError, "nonpublic_evidence_requires_governed_pipeline"):
            self.build(nodes=nodes, receipts=[])

    def test_policy_preview_denied_on_worker_role(self):
        p = self.build(request=request(actor_role="worker"))
        self.assertIn("policy_preview_not_allowed", p["review_holds"])
        self.assertEqual(p["hypervisor_policy_preview"]["decision"], "blocked")

    def test_cross_domain_task_mismatch_denied(self):
        with self.assertRaisesRegex(ValueError, "task_claim_domain_mismatch"):
            self.build(tasks=[candidate(domain="genomics")], receipts=[])

    def test_unknown_task_denied(self):
        with self.assertRaisesRegex(ValueError, "request_task_claim_mismatch"):
            self.build(request=request(task_id="other"))

    def test_wrong_receipt_plan_denied(self):
        forged = TaskResourceReceipt(
            task_id="task1", ring=1, seat=1, plan_sha256="0"*64,
            start=ProcessSnapshot(1, 1, 1, None), end=ProcessSnapshot(1, 2, 2, None),
            provider_usage=ProviderTokenUsage(1, 1), outcome="completed")
        with self.assertRaisesRegex(ValueError, "receipt_plan_scope_mismatch"):
            self.build(receipts=[forged])

    def test_noncanonical_numeric_identity_rejected(self):
        for bad in (0, "", "../foo", 4.5, []):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                request(trace_id=bad)

    def test_untrusted_role_rejected(self):
        with self.assertRaises(ValueError):
            request(actor_role="root-agent")

    def test_invalid_room_rejected(self):
        for bad in ("unknown-room", [], None):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                request(room_id=bad)

    def test_missing_public_room_permissions_denied(self):
        p = self.build(request=request(actor_role="debugger"))
        self.assertIn("policy_preview_not_allowed", p["review_holds"])

    def test_no_raw_source_group_or_digest_in_report(self):
        nodes = [evidence(1, source_group="very-private-marker"), evidence(2), evidence(3)]
        plan = plan_council72_review(nodes, self.tasks)
        p = self.build(nodes=nodes, receipts=[receipt(plan=plan)])
        blob = json.dumps(p)
        self.assertNotIn("very-private-marker", blob)
        self.assertNotIn("content_sha256", blob)
        self.assertNotIn('"source_group":', blob)

    def test_invalid_evidence_graph_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "missing_evidence_dependency"):
            self.build(nodes=[evidence(1, dependencies=("absent",)), evidence(2), evidence(3)])

    def test_invalid_tasks_fails_closed(self):
        with self.assertRaises(ValueError):
            self.build(tasks=[candidate(), candidate(2, seat=1)])

    def test_duplicate_resource_receipt_fails_closed(self):
        with self.assertRaises(ValueError):
            self.build(receipts=[self.receipts[0], self.receipts[0]])

    def test_verify_rejects_wrong_type(self):
        for bad in (None, [], "oops", True):
            self.assertFalse(verify_review_proof(bad, self.nodes, self.tasks, self.receipts,
                             self.request)["replay_matches"])

    def test_verify_rejects_unknown_added_field(self):
        p = self.build()
        p["unknown"] = "hello"
        self.assertFalse(verify_review_proof(p, self.nodes, self.tasks, self.receipts,
                         self.request)["replay_matches"])

    def test_invalid_parameter_bool_rejected(self):
        with self.assertRaises(ValueError):
            self.build(minimum_candidate_clusters=True)

    def test_never_promotes_to_execution_or_storage(self):
        import klone.proof_carrying_cognition_v29 as mod
        for name in ("approve", "activate", "publish", "write_memory", "execute", "serve"):
            self.assertFalse(hasattr(mod, name))
        p = self.build()
        for name in ("approval_granted", "memory_write_enabled", "publication_enabled",
                     "hypervisor_execution_authorized", "tasks_executed_by_this_module"):
            self.assertFalse(p[name])

try:
    from klone.council72_session import run_session, demo_session, validate_step
    from klone.council72_lineage_adapter_v26 import _nodes_from_normalized_observations
except ImportError:
    run_session = demo_session = validate_step = _nodes_from_normalized_observations = None


@unittest.skipUnless(run_session is not None, "full Council72 integration requires repository modules")
class ReviewProofV29RealCouncilIntegrationTests(unittest.TestCase):
    def test_replayed_synthetic_council_session_stays_unverified(self):
        session = run_session(demo_session())
        rows = [row for step in session["request"]["steps"]
                for row in validate_step(step)["observations"]]
        references = sorted({r["source_ref"] for r in rows})
        digests = {src: f"{i+1:064x}" for i, src in enumerate(references)}
        nodes = _nodes_from_normalized_observations(rows, digest_by_source_ref=digests)
        first = nodes[0]
        proposed = ReviewCandidate(task_id="task1", claim_key=first.claim_key,
                                   domain=first.domain, ring=1, seat=1, priority=100,
                                   estimated_tokens=100)
        req = request(claim_key=first.claim_key, room_id=first.room_id,
                      classification_level=first.classification)
        if any(n.room_id != "public-room" or n.classification != "public" for n in nodes):
            # A replaying Council72 fixture must NOT allow private metadata in
            # this deliberately public-only v2.9 report.
            with self.assertRaisesRegex(ValueError, "nonpublic_evidence_requires_governed_pipeline"):
                build_review_proof(nodes, [proposed], [], req)
        else:
            proof = build_review_proof(nodes, [proposed], [], req)
            self.assertFalse(proof["approval_granted"])
            self.assertFalse(proof["hypervisor_execution_authorized"])
            self.assertIn("telemetry_needs_review", proof["review_holds"])


if __name__ == "__main__":
    unittest.main()
