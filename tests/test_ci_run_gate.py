"""Offline verification of CI run identity and complete required jobs."""
import unittest

from klone.ci_run_gate import verify_ci_run


class CIRunGateTests(unittest.TestCase):
    def setUp(self):
        self.sha = "a" * 40
        self.run = {
            "id": 72, "run_attempt": 1, "head_sha": self.sha,
            "status": "completed", "conclusion": "success",
            "repository": {"full_name": "SickDinner/klone"},
        }
        self.jobs = [
            {"run_id": 72, "name": "linux", "status": "completed", "conclusion": "success"},
            {"run_id": 72, "name": "windows", "status": "completed", "conclusion": "success"},
        ]

    def verify(self, run=None, jobs=None, required=None):
        return verify_ci_run(
            self.run if run is None else run,
            self.jobs if jobs is None else jobs,
            repository="SickDinner/klone", expected_sha=self.sha,
            required_jobs={"linux", "windows"} if required is None else required,
        )

    def test_complete_success(self):
        result = self.verify()
        self.assertTrue(result["verified_success"])
        self.assertEqual(result["run_id"], "72")

    def test_run_identity_and_state_fail_closed(self):
        for key, value in (
            ("head_sha", "b" * 40),
            ("status", "in_progress"),
            ("conclusion", "failure"),
            ("run_attempt", None),
            ("id", 0),
            ("repository", {"full_name": "someone/else"}),
        ):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.verify(run={**self.run, key: value})

    def test_jobs_must_match_run_and_succeed(self):
        for key, value in (
            ("run_id", 999), ("status", "queued"), ("conclusion", "failure"),
        ):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.verify(jobs=[{**self.jobs[0], key: value}, self.jobs[1]])

    def test_missing_duplicate_or_empty_jobs_rejected(self):
        for jobs in ([], [self.jobs[0]], [self.jobs[0], self.jobs[0]]):
            with self.subTest(jobs=jobs), self.assertRaises(ValueError):
                self.verify(jobs=jobs)


if __name__ == "__main__":
    unittest.main()
