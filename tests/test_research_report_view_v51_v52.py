import unittest
from contextlib import redirect_stdout
from io import StringIO
import json

from klone.research_test_report import parse_summary
from klone.research_report_view import compare_observations, render_html, main


class ResearchReportViewV51V52(unittest.TestCase):
    def setUp(self):
        self.before = parse_summary("1045 passed, 1 skipped, 302 subtests passed in 116.27s",
                                    commit="a" * 40, exit_code=0)
        self.after = parse_summary("1055 passed, 1 skipped, 310 subtests passed in 114.40s",
                                   commit="b" * 40, exit_code=0)

    def test_count_deltas(self):
        result = compare_observations(self.before, self.after)
        self.assertEqual(result["count_delta"]["passed"], 10)
        self.assertEqual(result["count_delta"]["subtests_passed"], 8)
        self.assertEqual(result["count_delta"]["skipped"], 0)

    def test_comparability_is_not_assumed(self):
        result = compare_observations(self.before, self.after)
        self.assertFalse(result["comparability_verified"])
        self.assertFalse(result["independently_verified"])

    def test_failure_remains_visible(self):
        after = parse_summary("2 passed, 1 failed in 1.0s",
                              commit="c" * 40, exit_code=1)
        result = compare_observations(self.before, after)
        self.assertEqual(result["after_status"], "not_passed")
        self.assertEqual(result["count_delta"]["failed"], 1)

    def test_comparison_does_not_mutate_inputs(self):
        before = json.dumps(self.before, sort_keys=True)
        after = json.dumps(self.after, sort_keys=True)
        compare_observations(self.before, self.after)
        render_html(self.before, self.after)
        self.assertEqual(json.dumps(self.before, sort_keys=True), before)
        self.assertEqual(json.dumps(self.after, sort_keys=True), after)

    def test_html_contains_counts_and_limitations(self):
        page = render_html(self.before, self.after)
        self.assertIn("1045", page)
        self.assertIn("1055", page)
        self.assertIn("+10", page)
        self.assertIn("not independently verified", page)

    def test_html_escapes_display_fields(self):
        self.after["status"] = "<script>alert(1)</script>"
        page = render_html(self.before, self.after)
        self.assertNotIn("<script>", page)
        self.assertIn("&lt;script&gt;", page)

    def test_html_has_no_external_assets(self):
        page = render_html(self.before, self.after)
        self.assertNotIn("http://", page)
        self.assertNotIn("https://", page)
        self.assertNotIn("<script", page)

    def test_cli_json(self):
        out = StringIO()
        with redirect_stdout(out):
            result = main(["--before-commit", "a" * 40,
                           "--before-summary", "2 passed in 1.0s",
                           "--before-exit-code", "0",
                           "--after-commit", "b" * 40,
                           "--after-summary", "3 passed in 1.0s",
                           "--after-exit-code", "0"])
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(out.getvalue())["count_delta"]["passed"], 1)
