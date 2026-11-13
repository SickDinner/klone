"""Regression detection and evidence dashboard contract tests."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from klone.test_evidence_dashboard import compare_commits, summarize
from klone.test_evidence_ledger import EvidenceLedger


def record(commit, source, status, environment, run):
    return {
        "source": source, "run_id": run, "commit": commit, "status": status,
        "observed_at": "2026-11-12T16:00:00Z", "environment": environment,
    }


class EvidenceDashboardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = EvidenceLedger(Path(self.tmp.name) / "history.sqlite")
        self.ledger.initialize()
        self.old = "a" * 40
        self.new = "b" * 40

    def tearDown(self):
        self.tmp.cleanup()

    def test_detects_regression_and_improvement_separately(self):
        for item in (
            record(self.old, "github_actions", "success", "linux", "old-linux"),
            record(self.new, "github_actions", "failure", "linux", "new-linux"),
            record(self.old, "github_actions", "failure", "windows", "old-windows"),
            record(self.new, "github_actions", "success", "windows", "new-windows"),
        ):
            self.ledger.append(item)
        comparison = compare_commits(self.ledger, self.old, self.new)
        self.assertEqual(comparison["regressions"], [
            {"source": "github_actions", "environment": "linux", "reason": "success_to_failure"}
        ])
        self.assertEqual(comparison["improvements"], [
            {"source": "github_actions", "environment": "windows", "reason": "failure_to_success"}
        ])
        self.assertEqual(comparison["review_state"], "manual_review_required")

    def test_html_report_escapes_untrusted_environment_names(self):
        import importlib.util
        module_path = Path(__file__).resolve().parents[1] / "tools" / "test_evidence_dashboard.py"
        spec = importlib.util.spec_from_file_location("evidence_html", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.ledger.append(record(self.old, "github_actions", "success", "<script>alert(1)</script>", "old"))
        self.ledger.append(record(self.new, "github_actions", "failure", "<script>alert(1)</script>", "new"))
        html = module.render(summarize(self.ledger, self.new),
                             compare_commits(self.ledger, self.old, self.new))
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>", html)
        self.assertIn("success_to_failure", html)

    def test_missing_device_evidence_never_counts_as_approval(self):
        self.ledger.append(record(self.new, "github_actions", "success", "linux", "ci-1"))
        summary = summarize(self.ledger, self.new)
        self.assertEqual(summary["review_state"], "pending_evidence")
        self.assertEqual(summary["sources"]["termux_bridge"]["runs"], 0)
        self.assertEqual(summary["sources"]["github_actions"]["success"], 1)

    def test_missing_environment_is_reported_not_inferred(self):
        self.ledger.append(record(self.old, "github_actions", "success", "linux", "ci-old"))
        self.ledger.append(record(self.new, "termux_bridge", "success", "android", "device-new"))
        comparison = compare_commits(self.ledger, self.old, self.new)
        self.assertEqual(comparison["regressions"], [])
        self.assertEqual(comparison["missing_candidate_environments"], [
            {"source": "github_actions", "environment": "linux"}
        ])
        self.assertEqual(comparison["missing_baseline_environments"], [
            {"source": "termux_bridge", "environment": "android"}
        ])

    def v2(self, commit, status, run, context='c'*64, consistent=True, complete=True):
        item = record(commit, 'termux_bridge', status, 'android-unverified', run)
        item['details'] = {'manifest_schema_version':2, 'comparison_id':context,
                           'execution_context_consistent':consistent, 'collection_complete':complete}
        self.ledger.append(item)

    def test_v2_matching_complete_context_can_compare(self):
        self.v2(self.old, 'success', 'old')
        self.v2(self.new, 'failure', 'new')
        comparison = compare_commits(self.ledger,self.old,self.new)
        self.assertEqual(len(comparison['regressions']),1)
        self.assertEqual(comparison['unknown_contexts'],[])

    def test_v2_different_profiles_are_unknown_and_visible_in_html(self):
        self.v2(self.old, 'success', 'old')
        self.v2(self.new, 'failure', 'new', context='d'*64)
        comparison = compare_commits(self.ledger,self.old,self.new)
        self.assertEqual(comparison['regressions'],[])
        self.assertEqual(comparison['improvements'],[])
        self.assertEqual(len(comparison['unknown_contexts']),1)
        import importlib.util
        spec=importlib.util.spec_from_file_location('context_dashboard_html',Path(__file__).resolve().parents[1]/'tools/test_evidence_dashboard.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        page=module.render(summarize(self.ledger,self.new),comparison)
        self.assertIn('v2_context_unavailable_or_mismatched',page)

    def test_v2_incomplete_or_inconsistent_context_cannot_confirm(self):
        self.v2(self.old,'success','old',consistent=False)
        self.v2(self.new,'failure','new',complete=False)
        self.assertEqual(compare_commits(self.ledger,self.old,self.new)['regressions'],[])

    def test_mixed_v1_and_v2_cannot_confirm_a_ledger_regression(self):
        self.ledger.append(record(self.old,'termux_bridge','success','android-unverified','old'))
        self.v2(self.new,'failure','new')
        comparison=compare_commits(self.ledger,self.old,self.new)
        self.assertEqual(comparison['regressions'],[])
        self.assertEqual(len(comparison['unknown_contexts']),1)


if __name__ == "__main__":
    unittest.main()
