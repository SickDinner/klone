import unittest
from klone.termux_provenance_guard import verify_termux_issue_comment

class TermuxProvenanceGuardTests(unittest.TestCase):
    def setUp(self):
        self.repo = "SickDinner/klone"
        self.prefix = "https://api.github.com/repos/" + self.repo
        self.issue = {"number": 72, "repository_url": self.prefix,
                      "labels": [{"name": "klone-termux-task"}],
                      "user": {"login": "SickDinner"},
                      "body": '{"action":"tests"}'}
        self.comment = {"issue_url": self.prefix + "/issues/72",
                        "user": {"login": "SickDinner"},
                        "created_at": "2026-11-12T16:00:00Z",
                        "body": "KLONE Termux bridge result for `tests`\n\nTests: 12 in 1.2s; OK\n\nExit code: 0"}

    def verify(self, issue=None, comment=None):
        return verify_termux_issue_comment(
            issue=self.issue if issue is None else issue,
            comment=self.comment if comment is None else comment,
            repository=self.repo, trusted_actor="SickDinner",
            expected_action="tests", expected_commit="a" * 40)

    def test_github_actor_is_not_device_attestation(self):
        result = self.verify()
        self.assertTrue(result["github_actor_verified"])
        self.assertFalse(result["device_identity_verified"])
        self.assertFalse(result["commit_on_device_verified"])
        self.assertFalse(result["deployment_approval"])

    def test_untrusted_issue_or_comment_rejected(self):
        with self.assertRaises(ValueError):
            self.verify(issue={**self.issue, "user": {"login": "attacker"}})
        with self.assertRaises(ValueError):
            self.verify(comment={**self.comment, "user": {"login": "attacker"}})

    def test_wrong_repo_label_or_action_rejected(self):
        for change in ({"repository_url": "https://api.github.com/repos/other/repo"},
                       {"labels": []}, {"body": '{"action":"health"}'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.verify(issue={**self.issue, **change})

    def test_wrong_issue_and_duplicate_exit_rejected(self):
        with self.assertRaises(ValueError):
            self.verify(comment={**self.comment, "issue_url": self.prefix + "/issues/71"})
        with self.assertRaises(ValueError):
            self.verify(comment={**self.comment, "body": self.comment["body"] + "\nExit code: 0"})
