"""No-network tests for authenticated CI API fetcher."""
import io
import json
import unittest

from klone.github_ci_fetcher import fetch_ci_run_and_jobs


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class GitHubCIFetcherTests(unittest.TestCase):
    def setUp(self):
        self.paths = []

    def opener(self, request, timeout):
        self.assertEqual(timeout, 15)
        self.assertTrue(request.get_header("Authorization").startswith("Bearer "))
        self.paths.append(request.full_url)
        if "/jobs?" in request.full_url:
            payload = {"total_count": 2, "jobs": [{"id": 1}, {"id": 2}]}
        else:
            payload = {"id": 72, "head_sha": "a" * 40}
        return _Response(json.dumps(payload).encode())

    def test_fetches_exact_run_and_all_jobs(self):
        run, jobs = fetch_ci_run_and_jobs("SickDinner/klone", 72,
                                          token="dummy", opener=self.opener)
        self.assertEqual(run["id"], 72)
        self.assertEqual(len(jobs), 2)
        self.assertEqual(len(self.paths), 2)

    def test_invalid_repo_or_run_rejected_before_network(self):
        for repo, run in (("../evil", 72), ("SickDinner/klone", 0),
                          ("SickDinner/klone", True)):
            with self.subTest(repo=repo, run=run), self.assertRaises(ValueError):
                fetch_ci_run_and_jobs(repo, run, token="dummy", opener=self.opener)
        self.assertEqual(self.paths, [])

    def test_incomplete_job_page_fails_closed(self):
        def incomplete(req, timeout):
            if "/jobs?" in req.full_url:
                return _Response(b'{"total_count":101,"jobs":[]}')
            return _Response(b'{"id":72}')
        with self.assertRaisesRegex(ValueError, "incomplete"):
            fetch_ci_run_and_jobs("SickDinner/klone", 72,
                                  token="dummy", opener=incomplete)

    def test_http_failure_does_not_leak_token(self):
        def failing(req, timeout):
            raise RuntimeError("secret-token-here")
        with self.assertRaises(RuntimeError) as ctx:
            fetch_ci_run_and_jobs("SickDinner/klone", 72,
                                  token="secret-token-here", opener=failing)
        self.assertNotIn("secret-token-here", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
