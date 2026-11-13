import unittest
from klone.evidence_github_bridge import normalize, fetch

SHA = "a" * 40


def run(**changes):
    data = {"id": 42, "head_sha": SHA, "name": "KLONE regression guard",
            "run_attempt": 1, "repository": {"full_name": "SickDinner/klone"},
            "path": ".github/workflows/klone-regression.yml",
            "event": "push", "status": "completed", "conclusion": "success"}
    data.update(changes)
    return data


def listing(runs):
    return {"total_count": len(runs), "workflow_runs": runs}


class GitHubBridgeTests(unittest.TestCase):
    def test_successful_run(self):
        result = normalize(listing([run()]), SHA)
        self.assertEqual(result["conclusion"], "success")
        self.assertFalse(result["origin_authenticated"])
        self.assertFalse(result["deployment_approval"])

    def test_newest_matching_run(self):
        result = normalize(listing([run(id=10, conclusion="failure"), run(id=11)]), SHA)
        self.assertEqual(result["run_id"], 11)

    def test_wrong_commit_rejected(self):
        with self.assertRaises(ValueError):
            normalize(listing([run(head_sha="b" * 40)]), SHA)

    def test_wrong_workflow_rejected(self):
        with self.assertRaises(ValueError):
            normalize(listing([run(name="other")]), SHA)

    def test_in_progress_not_success(self):
        result = normalize(listing([run(status="in_progress", conclusion="success")]), SHA)
        self.assertIsNone(result["conclusion"])

    def test_bad_commit_rejected_before_network(self):
        with self.assertRaises(ValueError):
            fetch("SickDinner/klone", "not-a-commit")

    def test_unexpected_repository_rejected_before_network(self):
        with self.assertRaises(ValueError):
            fetch("other/repo", SHA)


if __name__ == "__main__":
    unittest.main()
