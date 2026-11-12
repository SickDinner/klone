import unittest
from unittest.mock import patch

from klone.evidence_one_command import run


class OneCommandTests(unittest.TestCase):
    def test_invalid_local_evidence_does_not_call_network(self):
        local = {"integrity_ok": False, "required_stages_passed": False,
                 "commit": None}
        def forbidden(*args):
            raise AssertionError("network must not be called")
        with patch("klone.evidence_one_command.inspect", return_value=local):
            result = run(None, None, github_fetch=forbidden)
        self.assertEqual(result["decision"], "blocked")
        self.assertIsNone(result["github"])

    def test_success_is_manual_only(self):
        commit = "a" * 40
        local = {"integrity_ok": True, "required_stages_passed": True,
                 "commit": commit, "stage_statuses": {
                     "syntax": "passed", "cognition": "passed",
                     "full": "passed", "local_deploy": "passed"}}
        def remote(repo, sha, token):
            self.assertEqual(sha, commit)
            return {"commit": commit, "workflow": "KLONE regression guard",
                    "conclusion": "success"}
        with patch("klone.evidence_one_command.inspect", return_value=local):
            result = run(None, None, github_fetch=remote)
        self.assertEqual(result["decision"], "manual_review_required")
        self.assertFalse(result["origin_authenticated"])
        self.assertFalse(result["deployment_approval"])

    def test_github_unavailable_blocks(self):
        local = {"integrity_ok": True, "required_stages_passed": True,
                 "commit": "a" * 40}
        def unavailable(*args):
            raise OSError("offline")
        with patch("klone.evidence_one_command.inspect", return_value=local):
            result = run(None, None, github_fetch=unavailable)
        self.assertEqual(result["decision"], "blocked")
        self.assertEqual(result["errors"], ["github_ci_unavailable:OSError"])


if __name__ == "__main__":
    unittest.main()
