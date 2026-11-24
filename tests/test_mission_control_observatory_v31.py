"""v3.1 read-only observatory: strict run claims, memory, replay, no authority."""
import copy
import json
import unittest
from unittest.mock import patch

from klone.acceptance_matrix import DOMAINS
from klone.memory_continuity_v30 import PublicMemoryEvent
from klone.mission_control_observatory_v31 import (
    RegressionRunClaim, ProofRebuildInputs,
    summarize_regression_claims, build_mission_control_review,
    verify_mission_control_review,
)

COMMIT = "1" * 40
OTHER = "2" * 40
DIGEST = "a" * 64
TIME = "2026-11-24T08:00:00Z"


def event(i, **extra):
    kw = dict(event_id=i, recorded_at=TIME, occurred_at=TIME)
    kw.update(extra)
    return PublicMemoryEvent(**kw)


def run(env, version, *, result="passed", sha=COMMIT, count=1400, skipped=2,
        digest=DIGEST):
    return RegressionRunClaim(
        environment=env, python_version=version, commit_sha=sha,
        test_count=count, skipped=skipped, result=result,
        source_kind="operator_log_claim" if env == "android" else "github_actions_claim",
        record_sha256=digest,
    )


def complete_runs():
    return (run("android", "3.13"), run("ubuntu", "3.11"),
            run("ubuntu", "3.12"), run("windows", "3.11"), run("windows", "3.12"))


def dashboard(*, states=None, before=None, after=None, runs=None, proof_inputs=None):
    return build_mission_control_review(
        expected_commit_sha=COMMIT,
        domain_states=dict.fromkeys(DOMAINS, "passed") if states is None else states,
        memory_before=[event(1)] if before is None else before,
        memory_after=[event(1)] if after is None else after,
        regression_claims=complete_runs() if runs is None else runs,
        proof_inputs=proof_inputs)


class RunClaimTests(unittest.TestCase):
    def test_full_matrix_claimed_only(self):
        m = summarize_regression_claims(complete_runs(), expected_commit_sha=COMMIT)
        self.assertTrue(m["complete_consistent_matrix_as_claimed"])
        self.assertFalse(m["run_origin_authenticated"])
        self.assertFalse(m["device_identity_authenticated"])
        self.assertFalse(m["ci_attestations_verified"])
        self.assertFalse(m["approval_granted"])

    def test_missing_matrix_key(self):
        m = summarize_regression_claims(complete_runs()[:-1], expected_commit_sha=COMMIT)
        self.assertEqual(m["missing_matrix_keys"], ["windows:3.12"])
        self.assertFalse(m["complete_consistent_matrix_as_claimed"])

    def test_no_runs_is_unverified_not_passed(self):
        m = summarize_regression_claims((), expected_commit_sha=COMMIT)
        self.assertEqual(len(m["missing_matrix_keys"]), 5)
        self.assertFalse(m["all_results_passed_as_claimed"])

    def test_duplicate_matrix_key_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "duplicate_regression_matrix_key"):
            summarize_regression_claims((run("android", "3.13"),
                                         run("android", "3.13")), expected_commit_sha=COMMIT)

    def test_mismatched_commit_remains_visible(self):
        m = summarize_regression_claims((run("android", "3.13", sha=OTHER),),
                                        expected_commit_sha=COMMIT)
        self.assertEqual(m["wrong_commit_matrix_keys"], ["android:3.13"])

    def test_failed_run_not_passed(self):
        m = summarize_regression_claims((run("android", "3.13", result="failed"),),
                                        expected_commit_sha=COMMIT)
        self.assertEqual(m["reported_failure_matrix_keys"], ["android:3.13"])

    def test_inconsistent_test_count(self):
        r = list(complete_runs())
        r[1] = run("ubuntu", "3.11", count=1399)
        self.assertTrue(summarize_regression_claims(r, expected_commit_sha=COMMIT)
                        ["test_count_disagreement"])

    def test_missing_digest_is_explicit_not_zero(self):
        m = summarize_regression_claims((run("android", "3.13", digest=None),),
                                        expected_commit_sha=COMMIT)
        self.assertEqual(m["missing_record_digest_keys"], ["android:3.13"])

    def test_permutation_stable(self):
        r = complete_runs()
        self.assertEqual(summarize_regression_claims(r, expected_commit_sha=COMMIT),
                         summarize_regression_claims(r[::-1], expected_commit_sha=COMMIT))

    def test_boolean_rejected_in_counts(self):
        with self.assertRaises(ValueError):
            run("android", "3.13", count=True)
        with self.assertRaises(ValueError):
            run("android", "3.13", skipped=False)

    def test_negative_or_excess_skips_rejected(self):
        for n in (-1, 1400, 1500):
            with self.subTest(n=n), self.assertRaises(ValueError):
                run("android", "3.13", skipped=n)

    def test_unknown_result_rejected(self):
        with self.assertRaises(ValueError):
            run("android", "3.13", result="success✅")

    def test_source_claim_must_match_environment(self):
        with self.assertRaisesRegex(ValueError, "android_origin_claim_mismatch"):
            RegressionRunClaim("android", "3.13", COMMIT, 10, 1, "passed",
                               "github_actions_claim")
        with self.assertRaisesRegex(ValueError, "ci_origin_claim_mismatch"):
            RegressionRunClaim("ubuntu", "3.12", COMMIT, 10, 1, "passed",
                               "operator_log_claim")

    def test_unknown_python_and_platform_rejected(self):
        for env, ver in (("macos", "3.11"), ("ubuntu", "3.14"),
                         ("android", "3.11"), ("windows", "3.13")):
            with self.subTest(env=env, ver=ver), self.assertRaises(ValueError):
                run(env, ver)

    def test_malformed_hashes_rejected(self):
        with self.assertRaises(ValueError):
            run("android", "3.13", sha="b" * 39)
        with self.assertRaises(ValueError):
            run("android", "3.13", digest="X" * 64)
        with self.assertRaises(ValueError):
            summarize_regression_claims((), expected_commit_sha="X" * 40)

    def test_invalid_collection_and_oversized_denied(self):
        for x in (None, "text", [None], [1] * 9):
            with self.subTest(v=repr(x)), self.assertRaises(ValueError):
                summarize_regression_claims(x, expected_commit_sha=COMMIT)

    def test_report_does_not_copy_digest_or_raw_source(self):
        result = summarize_regression_claims(complete_runs(), expected_commit_sha=COMMIT)
        self.assertNotIn(DIGEST, json.dumps(result))
        self.assertIn("record_digest_supplied", json.dumps(result))

    def test_different_digest_changes_fingerprint(self):
        a = summarize_regression_claims((run("android", "3.13", digest="a" * 64),),
                                        expected_commit_sha=COMMIT)
        b = summarize_regression_claims((run("android", "3.13", digest="b" * 64),),
                                        expected_commit_sha=COMMIT)
        self.assertNotEqual(a["matrix_sha256"], b["matrix_sha256"])


class DashboardTests(unittest.TestCase):
    def test_complete_matrix_is_not_deployment(self):
        r = dashboard()
        self.assertEqual(r["review_status"], "manual_review_required")
        self.assertFalse(r["report_sources_authenticated"])
        self.assertFalse(r["memory_snapshot_completeness_verified"])
        self.assertFalse(r["production_readiness_verified"])
        self.assertFalse(r["deployment_approval"])
        self.assertFalse(r["permission_granted"])
        self.assertFalse(r["tasks_dispatched"])
        self.assertFalse(r["service_health_checked"])
        self.assertFalse(r["live_agent_telemetry_measured"])
        self.assertFalse(r["external_audit_anchor_verified"])

    def test_memory_history_disappears_blocks(self):
        r = dashboard(before=[event(1), event(2)], after=[event(2)])
        self.assertEqual(r["review_status"], "blocked_for_review")
        self.assertIn("memory_continuity_conflict", r["review_reasons"])

    def test_corrected_event_reactivated_blocks(self):
        corrected = event(1, status="rejected", corrected_at="2026-11-24T09:00:00Z",
                          correction_reason="correction", corrected_by_role="owner")
        r = dashboard(before=[corrected], after=[event(1)])
        self.assertEqual(r["review_status"], "blocked_for_review")

    def test_failed_regression_blocks(self):
        runs = list(complete_runs())
        runs[4] = run("windows", "3.12", result="failed")
        self.assertIn("regression_reported_failure", dashboard(runs=runs)["review_reasons"])
        self.assertEqual(dashboard(runs=runs)["review_status"], "blocked_for_review")

    def test_commit_mismatch_blocks(self):
        runs = list(complete_runs())
        runs[0] = run("android", "3.13", sha=OTHER)
        self.assertIn("regression_commit_mismatch", dashboard(runs=runs)["review_reasons"])
        self.assertEqual(dashboard(runs=runs)["review_status"], "blocked_for_review")

    def test_incomplete_matrix_review_not_success(self):
        r = dashboard(runs=complete_runs()[:-1])
        self.assertIn("regression_matrix_incomplete", r["review_reasons"])
        self.assertFalse(r["regression"]["complete_consistent_matrix_as_claimed"])

    def test_domain_failed_does_not_get_green(self):
        states = dict.fromkeys(DOMAINS, "passed")
        states["hypervisor"] = "failed"
        self.assertIn("domain:hypervisor", dashboard(states=states)["review_reasons"])

    def test_requires_all_12_domains(self):
        with self.assertRaises(ValueError):
            dashboard(states={"memory": "passed"})

    def test_invalid_nonpublic_memory_denied(self):
        with self.assertRaises(ValueError):
            event(1, room_id="sealed-room", classification_level="intimate")

    def test_no_raw_memory_data_or_opaque_paths(self):
        r = dashboard()
        raw = json.dumps(r)
        self.assertNotIn("evidence_text", raw)
        self.assertNotIn("~/", raw)
        self.assertNotIn("source_ref", raw)

    def test_output_is_deterministic(self):
        self.assertEqual(dashboard(), dashboard())

    def test_report_replays(self):
        r = dashboard()
        self.assertTrue(verify_mission_control_review(
            r, expected_commit_sha=COMMIT,
            domain_states=dict.fromkeys(DOMAINS, "passed"),
            memory_before=[event(1)], memory_after=[event(1)],
            regression_claims=complete_runs()))

    def test_tamper_detected(self):
        r = dashboard()
        r["review_status"] = "production_approved"
        self.assertFalse(verify_mission_control_review(
            r, expected_commit_sha=COMMIT,
            domain_states=dict.fromkeys(DOMAINS, "passed"),
            memory_before=[event(1)], memory_after=[event(1)],
            regression_claims=complete_runs()))

    def test_changed_input_detected(self):
        r = dashboard()
        x = list(complete_runs())
        x[-1] = run("windows", "3.12", result="failed")
        self.assertFalse(verify_mission_control_review(
            r, expected_commit_sha=COMMIT,
            domain_states=dict.fromkeys(DOMAINS, "passed"),
            memory_before=[event(1)], memory_after=[event(1)],
            regression_claims=x))

    def test_proof_missing_explicitly(self):
        r = dashboard()
        self.assertEqual(r["council_proof"]["review_status"], "not_supplied")
        self.assertIn("council_proof_not_supplied", r["review_reasons"])

    def test_proof_recomputed_and_minimal_summary(self):
        inp = ProofRebuildInputs((), (), (), object())
        fake = {"report_sha256": "3" * 64,
                "review_status": "unverified_packet_ready_for_manual_review",
                "review_holds": []}
        with patch("klone.proof_carrying_cognition_v29.build_review_proof", return_value=fake) as f:
            r = dashboard(proof_inputs=inp)
        f.assert_called_once()
        self.assertTrue(r["council_proof"]["recomputed_from_original_inputs"])
        self.assertEqual(r["council_proof"]["report_sha256"], "3" * 64)
        self.assertFalse(r["council_proof"]["execution_authorized"])
        self.assertNotIn("task_id", json.dumps(r))

    def test_proof_holds_block_review(self):
        inp = ProofRebuildInputs((), (), (), object())
        fake = {"report_sha256": "3" * 64, "review_status": "hold_for_manual_review",
                "review_holds": ["telemetry_needs_review"]}
        with patch("klone.proof_carrying_cognition_v29.build_review_proof", return_value=fake):
            r = dashboard(proof_inputs=inp)
        self.assertEqual(r["review_status"], "blocked_for_review")
        self.assertIn("council_proof_requires_review", r["review_reasons"])

    def test_invalid_proof_struct_denied(self):
        for x in (None, "test", {}, object()):
            if x is None:
                continue
            with self.subTest(v=type(x).__name__), self.assertRaises(ValueError):
                dashboard(proof_inputs=x)
        with self.assertRaises(ValueError):
            ProofRebuildInputs([], (), (), object())

    def test_invalid_serialization_replay_false(self):
        r = dashboard()
        r["evil"] = {1, 2}
        self.assertFalse(verify_mission_control_review(
            r, expected_commit_sha=COMMIT,
            domain_states=dict.fromkeys(DOMAINS, "passed"),
            memory_before=[event(1)], memory_after=[event(1)]))

    def test_wrong_claim_type_denied(self):
        with self.assertRaises(ValueError):
            dashboard(runs=[{"environment": "android", "result": "passed"}])

    def test_no_extra_authority_interfaces(self):
        import klone.mission_control_observatory_v31 as module
        for method in ("approve", "authorize", "publish", "execute", "write_memory", "start_service"):
            self.assertFalse(hasattr(module, method))


try:
    from klone.hypervisor_runtime import HypervisorRuntime as _RealRuntime
except ImportError:
    _RealRuntime = None


@unittest.skipIf(_RealRuntime is None, "Full KLONE hypervisor dependencies required")
class RealV29IntegrationTests(unittest.TestCase):
    def test_true_v29_rebuild_never_approves(self):
        from klone.evidence_lineage_v26 import EvidenceLineageNode
        from klone.council72_portfolio_v26 import ReviewCandidate, plan_council72_review
        from klone.cognition_metabolism_v28 import (
            ProcessSnapshot, ProviderTokenUsage, TaskResourceReceipt)
        from klone.proof_carrying_cognition_v29 import ReviewProofRequest
        nodes = tuple(EvidenceLineageNode(
            node_id=f"n{i}", claim_key="claim1", domain="research",
            source_group=f"group{i}", content_sha256=f"{i:064x}",
            stance="supports", room_id="public-room", classification="public")
            for i in range(1, 4))
        tasks = (ReviewCandidate(task_id="task1", claim_key="claim1",
                domain="research", ring=1, seat=1, priority=90, estimated_tokens=100),)
        plan = plan_council72_review(nodes, tasks)
        receipt = TaskResourceReceipt(
            task_id="task1", ring=1, seat=1, plan_sha256=plan["plan_sha256"],
            start=ProcessSnapshot(pid=123, monotonic_ns=100,
                                  process_cpu_ns=10, current_rss_bytes=2048),
            end=ProcessSnapshot(pid=123, monotonic_ns=130,
                                process_cpu_ns=20, current_rss_bytes=3072),
            provider_usage=ProviderTokenUsage(10, 20), outcome="completed")
        proof_inputs = ProofRebuildInputs(
            nodes=nodes, tasks=tasks, receipts=(receipt,),
            request=ReviewProofRequest(task_id="task1", claim_key="claim1",
                       room_id="public-room", classification_level="public",
                       actor_role="evaluator", trace_id="trace1"))
        report = dashboard(proof_inputs=proof_inputs)
        self.assertTrue(report["council_proof"]["recomputed_from_original_inputs"])
        self.assertEqual(report["council_proof"]["review_status"],
                         "unverified_packet_ready_for_manual_review")
        self.assertFalse(report["permission_granted"])
        self.assertFalse(report["production_readiness_verified"])
        self.assertFalse(report["council_proof"]["execution_authorized"])
        self.assertTrue(verify_mission_control_review(
            report, expected_commit_sha=COMMIT,
            domain_states=dict.fromkeys(DOMAINS, "passed"),
            memory_before=[event(1)], memory_after=[event(1)],
            regression_claims=complete_runs(), proof_inputs=proof_inputs))


if __name__ == "__main__":
    unittest.main()
