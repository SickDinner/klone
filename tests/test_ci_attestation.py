import unittest

from klone.ci_attestation import attest_ci_payload


class CIAttestationTests(unittest.TestCase):
    def setUp(self):
        self.sha = "a" * 40
        self.run = {"id": 72, "run_attempt": 1, "head_sha": self.sha,
                    "status": "completed", "conclusion": "success",
                    "repository": {"full_name": "SickDinner/klone"}}
        self.jobs = [{"run_id": 72, "name": "linux", "status": "completed",
                      "conclusion": "success"}]

    def test_successful_ci_never_approves_deployment(self):
        result = attest_ci_payload(
            self.run, self.jobs, repository="SickDinner/klone",
            expected_sha=self.sha, required_jobs={"linux"},
        )
        self.assertEqual(result["ci_consistency"], "passed")
        self.assertFalse(result["deployment_approval"])
        self.assertTrue(result["manual_review_required"])
        self.assertEqual(result["android_attestation"], "not_verified")

    def test_failed_job_is_rejected(self):
        jobs = [{**self.jobs[0], "conclusion": "failure"}]
        with self.assertRaises(ValueError):
            attest_ci_payload(self.run, jobs, repository="SickDinner/klone",
                              expected_sha=self.sha, required_jobs={"linux"})


if __name__ == "__main__":
    unittest.main()
