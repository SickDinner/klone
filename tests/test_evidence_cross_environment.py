import unittest

from klone.evidence_cross_environment import compare


SHA = "a" * 40


def android(**changes):
    value = {
        "commit": SHA, "integrity_ok": True,
        "required_stages_passed": True,
        "stage_statuses": {
            "syntax": "passed", "cognition": "passed",
            "full": "passed", "local_deploy": "passed",
            "torch_probe": "not_present",
        },
    }
    value.update(changes)
    return value


def github(**changes):
    value = {"commit": SHA, "conclusion": "success",
             "workflow": "KLONE regression guard"}
    value.update(changes)
    return value


class CrossEnvironmentTests(unittest.TestCase):
    def test_matching_claims_manual_only(self):
        result = compare(android(), github())
        self.assertTrue(result["consistent_claims"])
        self.assertFalse(result["origin_authenticated"])
        self.assertFalse(result["deployment_approval"])
        self.assertEqual(result["decision"], "manual_review_required")

    def test_commit_mismatch_blocks(self):
        self.assertIn("commit_mismatch", compare(android(), github(commit="b" * 40))["errors"])

    def test_android_integrity_failure_blocks(self):
        self.assertEqual(compare(android(integrity_ok=False), github())["decision"], "blocked")

    def test_android_stage_failure_blocks(self):
        stages = android()["stage_statuses"]
        stages["full"] = "failed"
        self.assertIn("android_required_stage_mismatch",
                      compare(android(stage_statuses=stages), github())["errors"])

    def test_github_failure_blocks(self):
        self.assertIn("github_ci_not_success",
                      compare(android(), github(conclusion="failure"))["errors"])

    def test_unknown_workflow_blocks(self):
        self.assertIn("unexpected_workflow",
                      compare(android(), github(workflow="unknown"))["errors"])

    def test_invalid_commit_blocks(self):
        self.assertIn("invalid_android_commit",
                      compare(android(commit="not-a-sha"), github())["errors"])


if __name__ == "__main__":
    unittest.main()
