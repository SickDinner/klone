import unittest
from klone.research_test_report import parse_summary

SHA = "7f5e9a2336875f050c18b8784bdce1cfb83bded0"


class ResearchTestReportV50(unittest.TestCase):
    def parse(self, summary, exit_code=0):
        return parse_summary(summary, commit=SHA, exit_code=exit_code)

    def test_realistic_android_summary(self):
        report = self.parse("1045 passed, 1 skipped, 1 warning, 302 subtests passed in 116.27s (0:01:56)")
        self.assertEqual(report["counts"]["passed"], 1045)
        self.assertEqual(report["counts"]["subtests_passed"], 302)
        self.assertEqual(report["counts"]["skipped"], 1)
        self.assertEqual(report["counts"]["warnings"], 1)
        self.assertEqual(report["duration_seconds"], "116.27")
        self.assertEqual(report["status"], "passed_with_exclusions")
        self.assertFalse(report["independently_verified"])

    def test_clean_run(self):
        self.assertEqual(self.parse("3 passed in 0.10s")["status"], "passed")

    def test_failed_exit(self):
        self.assertEqual(self.parse("3 passed in 0.10s", 2)["status"], "not_passed")

    def test_reported_failure(self):
        self.assertEqual(self.parse("3 passed, 1 failed in 0.10s")["status"], "not_passed")

    def test_subtest_failure(self):
        self.assertEqual(self.parse("3 passed, 1 subtests failed in 0.10s")["status"], "not_passed")

    def test_no_passes_requires_review(self):
        self.assertEqual(self.parse("3 skipped in 0.10s")["status"], "review_required")

    def test_expected_and_unexpected_outcomes(self):
        self.assertEqual(self.parse("3 passed, 1 xfailed in 0.10s")["status"], "passed_with_exclusions")
        self.assertEqual(self.parse("3 passed, 1 xpassed in 0.10s")["status"], "review_required")

    def test_rejects_invalid_summary(self):
        for value in ("", "3 passed, 2 passed in 0.1s", "3 invented in 0.1s",
                      "3 warnings in 0.1s", "3 passed\n4 passed in 0.1s"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.parse(value)

    def test_rejects_invalid_metadata(self):
        for sha, code in (("main", 0), (SHA, -1), (SHA, True)):
            with self.subTest(sha=sha, code=code):
                with self.assertRaises(ValueError):
                    parse_summary("3 passed in 0.1s", commit=sha, exit_code=code)

    def test_report_is_repeatable(self):
        a = self.parse("=== 3 passed in 0.1s ===")
        b = self.parse("3 passed in 0.1s")
        self.assertEqual(a, b)
