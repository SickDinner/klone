import unittest

from klone.evidence_observatory import compare_history, render


def run(name, syntax="passed", integrity=True):
    return {
        "run_name": name, "commit": "a" * 40,
        "integrity_ok": integrity, "required_stages_passed": syntax == "passed",
        "stage_statuses": {
            "syntax": syntax, "cognition": "passed",
            "full": "passed", "local_deploy": "passed",
            "torch_probe": "not_present",
        },
        "errors": [], "decision": "manual_review_required" if integrity else "blocked",
    }


class ObservatoryDiffTests(unittest.TestCase):
    def test_regression_detected(self):
        changes = compare_history([run("old"), run("new", "failed")])
        self.assertEqual(changes[0]["regressed_stages"], ["syntax"])
        self.assertEqual(changes[0]["recovered_stages"], [])
        self.assertTrue(changes[0]["manual_review_required"])

    def test_recovery_detected(self):
        changes = compare_history([run("old", "failed"), run("new")])
        self.assertEqual(changes[0]["recovered_stages"], ["syntax"])

    def test_single_run_has_no_comparison(self):
        self.assertEqual(compare_history([run("only")]), [])

    def test_bad_integrity_not_comparable(self):
        changes = compare_history([run("old", integrity=False), run("new")])
        self.assertFalse(changes[0]["comparable"])

    def test_diff_html_escapes_names(self):
        page = render([run("<script>"), run("new")])
        self.assertNotIn("<script>", page)
        self.assertIn("&lt;script&gt;", page)


if __name__ == "__main__":
    unittest.main()
