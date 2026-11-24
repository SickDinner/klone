"""Deterministic Council72 metabolism accounting; no real agent execution."""
import json
import unittest
from dataclasses import replace
from unittest.mock import patch

from klone.cognition_metabolism_v28 import (
    ProcessSnapshot, ProviderTokenUsage, TaskResourceReceipt,
    capture_process_snapshot, reconcile_council_metabolism,
)
from klone.council72_portfolio_v26 import ReviewCandidate, plan_council72_review
from klone.evidence_lineage_v26 import EvidenceLineageNode


def node(i, **changes):
    fields = dict(node_id=f"n{i}", claim_key="claim", domain="cognition",
                  source_group=f"source{i}", content_sha256=f"{i:064x}",
                  stance="supports", room_id="public-room", classification="public")
    fields.update(changes)
    return EvidenceLineageNode(**fields)


def task(i, ring, *, estimate=100):
    return ReviewCandidate(task_id=f"task{i}", claim_key="claim", domain="cognition",
                           ring=ring, seat=1, priority=10, estimated_tokens=estimate)


def snap(t, cpu=None, pid=20, rss=4096):
    return ProcessSnapshot(pid=pid, monotonic_ns=t, process_cpu_ns=t if cpu is None else cpu,
                           current_rss_bytes=rss)


def receipt(plan, task_id="task1", ring=1, start=100, end=200, usage=(25, 40),
            outcome="completed", pid=20, rss=8192):
    return TaskResourceReceipt(task_id, ring, 1, plan["plan_sha256"],
                               snap(start, pid=pid), snap(end, pid=pid, rss=rss),
                               ProviderTokenUsage(*usage), outcome)


class ProcessSamplingTests(unittest.TestCase):
    def test_real_os_sample_has_consistent_fields(self):
        sample = capture_process_snapshot()
        self.assertGreater(sample.pid, 0)
        self.assertGreater(sample.monotonic_ns, 0)
        self.assertGreaterEqual(sample.process_cpu_ns, 0)
        self.assertTrue(sample.current_rss_bytes is None or sample.current_rss_bytes > 0)

    def test_deterministic_sample(self):
        with (patch("klone.cognition_metabolism_v28.os.getpid", return_value=72),
              patch("klone.cognition_metabolism_v28.time.monotonic_ns", return_value=100),
              patch("klone.cognition_metabolism_v28.time.process_time_ns", return_value=12),
              patch("klone.cognition_metabolism_v28._self_rss_bytes", return_value=None)):
            self.assertEqual(capture_process_snapshot(), ProcessSnapshot(72, 100, 12, None))

    def test_missing_rss_is_unknown_not_zero(self):
        self.assertIsNone(ProcessSnapshot(1, 2, 3, None).current_rss_bytes)

    def test_negative_pid_denied(self):
        with self.assertRaises(ValueError):
            ProcessSnapshot(0, 1, 1, None)

    def test_bool_pid_denied(self):
        with self.assertRaises(ValueError):
            ProcessSnapshot(True, 1, 1, None)

    def test_negative_clock_denied(self):
        with self.assertRaises(ValueError):
            ProcessSnapshot(1, -1, 1, None)

    def test_bool_clock_denied(self):
        with self.assertRaises(ValueError):
            ProcessSnapshot(1, True, 1, None)

    def test_negative_rss_denied(self):
        with self.assertRaises(ValueError):
            ProcessSnapshot(1, 2, 3, -1)

    def test_missing_provider_usage_is_none(self):
        self.assertIsNone(ProviderTokenUsage(None, None).total)

    def test_zero_usage_is_valid_explicit_report(self):
        self.assertEqual(ProviderTokenUsage(0, 0).total, 0)

    def test_partial_provider_usage_denied(self):
        with self.assertRaisesRegex(ValueError, "incomplete"):
            ProviderTokenUsage(0, None)

    def test_bool_provider_usage_denied(self):
        with self.assertRaises(ValueError):
            ProviderTokenUsage(True, 0)

    def test_too_many_reported_tokens_denied(self):
        with self.assertRaises(ValueError):
            ProviderTokenUsage(8_000_000, 8_000_000)

    def test_different_process_snapshots_denied(self):
        plan = build_plan()
        with self.assertRaisesRegex(ValueError, "different_process"):
            TaskResourceReceipt("task1", 1, 1, plan["plan_sha256"],
                                snap(1, pid=20), snap(2, pid=21),
                                ProviderTokenUsage(1, 2), "completed")

    def test_clock_going_back_denied(self):
        plan = build_plan()
        with self.assertRaisesRegex(ValueError, "non_monotonic"):
            receipt(plan, start=200, end=100)

    def test_invalid_outcome_denied(self):
        plan = build_plan()
        with self.assertRaisesRegex(ValueError, "invalid_receipt_outcome"):
            receipt(plan, outcome="approved")

    def test_invalid_ring_denied(self):
        plan = build_plan()
        with self.assertRaises(ValueError):
            receipt(plan, ring=10)


def build_plan(*, include_second=False, total=150, ring_limit=100, contested=False, estimate=None):
    nodes = [node(1), node(2)] + ([node(3, stance="contradicts")] if contested else [])
    estimate = (70 if include_second else 100) if estimate is None else estimate
    tasks = [task(1, 1, estimate=estimate)] + ([task(2, 2, estimate=estimate)] if include_second else [])
    return plan_council72_review(nodes, tasks, max_total_tokens=total,
                                 max_ring_tokens=ring_limit)


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.plan = build_plan()

    def test_within_budget_for_review_only(self):
        r = reconcile_council_metabolism(self.plan, [receipt(self.plan)])
        self.assertEqual(r["review_status"], "within_reported_budgets_for_review")
        self.assertEqual(r["reported_token_total_known_only"], 65)
        self.assertEqual(r["reported_tokens_per_ring_known_only"]["1"], 65)
        self.assertEqual(r["cpu_total_ns_if_nonoverlapping"], 100)
        self.assertEqual(r["rss_samples_available"], 1)
        self.assertFalse(r["telemetry_authenticated"])
        self.assertFalse(r["resource_limit_enforced"])
        self.assertFalse(r["approval_granted"])
        self.assertFalse(r["execution_enabled"])

    def test_token_budget_overrun_is_not_silenced(self):
        plan = build_plan(estimate=80)
        r = reconcile_council_metabolism(plan, [receipt(plan, usage=(40, 50))])
        self.assertEqual(r["review_status"], "task_estimate_exceeded")
        self.assertEqual(r["estimate_exceeded_task_ids"], ["task1"])

    def test_ring_budget_overshoot_detected(self):
        r = reconcile_council_metabolism(self.plan, [receipt(self.plan, usage=(100, 1))])
        self.assertEqual(r["review_status"], "reported_budget_exceeded")

    def test_total_budget_overshoot_detected(self):
        plan = build_plan(include_second=True, total=150, ring_limit=100)
        receipts = [receipt(plan, "task1", 1, usage=(90, 5), pid=10),
                    receipt(plan, "task2", 2, usage=(90, 5), pid=11)]
        r = reconcile_council_metabolism(plan, receipts)
        self.assertEqual(r["review_status"], "reported_budget_exceeded")
        self.assertEqual(r["reported_token_total_known_only"], 190)

    def test_zero_receipts_means_missing_not_zero(self):
        r = reconcile_council_metabolism(self.plan, [])
        self.assertEqual(r["review_status"], "insufficient_telemetry")
        self.assertEqual(r["missing_task_ids"], ["task1"])

    def test_missing_provider_usage_means_insufficient(self):
        r = reconcile_council_metabolism(self.plan, [receipt(self.plan, usage=(None, None))])
        self.assertEqual(r["review_status"], "insufficient_telemetry")
        self.assertEqual(r["missing_provider_usage_task_ids"], ["task1"])
        self.assertEqual(r["reported_token_total_known_only"], 0)

    def test_failed_task_never_seen_as_success(self):
        r = reconcile_council_metabolism(self.plan, [receipt(self.plan, outcome="failed")])
        self.assertEqual(r["review_status"], "incomplete_or_failed_work")

    def test_cancelled_task_is_incomplete(self):
        r = reconcile_council_metabolism(self.plan, [receipt(self.plan, outcome="cancelled")])
        self.assertEqual(r["review_status"], "incomplete_or_failed_work")

    def test_duplicate_receipt_denied(self):
        r = receipt(self.plan)
        with self.assertRaisesRegex(ValueError, "duplicate_resource_receipt"):
            reconcile_council_metabolism(self.plan, [r, r])

    def test_unknown_task_denied(self):
        with self.assertRaisesRegex(ValueError, "receipt_for_unqueued"):
            reconcile_council_metabolism(self.plan, [receipt(self.plan, task_id="alien")])

    def test_denied_plan_task_never_accepted_as_execution(self):
        plan = build_plan(contested=True)
        self.assertEqual(plan["queued_task_count"], 0)
        with self.assertRaisesRegex(ValueError, "receipt_for_unqueued"):
            reconcile_council_metabolism(plan, [receipt(plan)])

    def test_receipt_plan_hash_mismatch_denied(self):
        r = replace(receipt(self.plan), plan_sha256="1"*64)
        with self.assertRaisesRegex(ValueError, "receipt_plan_scope_mismatch"):
            reconcile_council_metabolism(self.plan, [r])

    def test_ring_mismatch_denied(self):
        with self.assertRaisesRegex(ValueError, "receipt_plan_scope_mismatch"):
            reconcile_council_metabolism(self.plan, [receipt(self.plan, ring=2)])

    def test_modified_planned_budget_denied_even_with_old_digest(self):
        plan = dict(self.plan, max_total_tokens=999999)
        with self.assertRaisesRegex(ValueError, "invalid_portfolio_integrity"):
            reconcile_council_metabolism(plan, [])

    def test_overlapping_same_pid_not_counted_as_additive_cpu(self):
        plan = build_plan(include_second=True, total=200)
        receipts = [receipt(plan, "task1", 1, start=100, end=200),
                    receipt(plan, "task2", 2, start=150, end=300)]
        r = reconcile_council_metabolism(plan, receipts)
        self.assertEqual(r["review_status"], "process_intervals_overlap")
        self.assertIsNone(r["cpu_total_ns_if_nonoverlapping"])

    def test_different_pids_allow_overlapping_windows(self):
        plan = build_plan(include_second=True, total=200)
        receipts = [receipt(plan, "task1", 1, start=100, end=200, pid=10),
                    receipt(plan, "task2", 2, start=150, end=300, pid=11)]
        r = reconcile_council_metabolism(plan, receipts)
        self.assertEqual(r["review_status"], "within_reported_budgets_for_review")
        self.assertEqual(r["cpu_total_ns_if_nonoverlapping"], 250)

    def test_report_permutation_invariant(self):
        plan = build_plan(include_second=True, total=200)
        receipts = [receipt(plan, "task1", 1, pid=10), receipt(plan, "task2", 2, pid=11)]
        self.assertEqual(reconcile_council_metabolism(plan, receipts),
                         reconcile_council_metabolism(plan, list(reversed(receipts))))

    def test_hash_changes_when_measurement_changes(self):
        before = reconcile_council_metabolism(self.plan, [receipt(self.plan, end=200)])
        after = reconcile_council_metabolism(self.plan, [receipt(self.plan, end=201)])
        self.assertNotEqual(before["report_sha256"], after["report_sha256"])

    def test_no_raw_evidence_content_in_report(self):
        report = reconcile_council_metabolism(self.plan, [receipt(self.plan)])
        self.assertNotIn("content_sha256", json.dumps(report))
        self.assertNotIn("source_group", json.dumps(report))

    def test_no_dispatch_or_approval_api(self):
        import klone.cognition_metabolism_v28 as module
        for api in ("execute", "approve", "publish", "dispatch", "write_memory", "run_agent"):
            self.assertFalse(hasattr(module, api))

    def test_unknown_receipt_collection_denied(self):
        with self.assertRaisesRegex(ValueError, "invalid_resource_receipts"):
            reconcile_council_metabolism(self.plan, "untrusted")

    def test_missing_rss_not_replaced_with_zero(self):
        r = reconcile_council_metabolism(self.plan, [receipt(self.plan, rss=None)])
        self.assertIsNone(r["rows"][0]["process_current_rss_bytes_after"])
        self.assertEqual(r["rss_samples_available"], 0)

    def test_boolean_schema_version_with_matching_digest_denied(self):
        from klone.cognition_metabolism_v28 import _json_bytes
        from hashlib import sha256
        altered = dict(self.plan, schema_version=True)
        altered["plan_sha256"] = sha256(_json_bytes({k: v for k, v in altered.items()
                                                   if k != "plan_sha256"})).hexdigest()
        with self.assertRaisesRegex(ValueError, "invalid_portfolio_artifact"):
            reconcile_council_metabolism(altered, [])

    def test_unhashable_queue_result_denied_cleanly(self):
        from klone.cognition_metabolism_v28 import _json_bytes
        from hashlib import sha256
        altered = dict(self.plan)
        altered["tasks"] = [dict(altered["tasks"][0], queue_result=["queued_for_human_review_only"])]
        altered["plan_sha256"] = sha256(_json_bytes({k: v for k, v in altered.items()
                                                   if k != "plan_sha256"})).hexdigest()
        with self.assertRaisesRegex(ValueError, "invalid_portfolio_decision"):
            reconcile_council_metabolism(altered, [])

    def test_unmodified_plan_fingerprint_is_not_authentication(self):
        r = reconcile_council_metabolism(self.plan, [receipt(self.plan)])
        self.assertEqual(r["plan_sha256"], self.plan["plan_sha256"])
        self.assertFalse(r["telemetry_authenticated"])

    def test_resource_report_is_deterministic_with_unknown_usage(self):
        a = reconcile_council_metabolism(self.plan, [receipt(self.plan, usage=(None, None))])
        b = reconcile_council_metabolism(self.plan, [receipt(self.plan, usage=(None, None))])
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
