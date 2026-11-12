"""GitHub Actions evidence adapter regression tests."""
import unittest

from klone.test_evidence_adapters import normalize_github_manifest


class GithubEvidenceAdapterTests(unittest.TestCase):
    def setUp(self):
        self.sha = "a" * 40
        self.manifest = {
            "schema_version": 1, "source": "github_actions",
            "run_id": "123", "run_attempt": 1,
            "commit": self.sha, "status": "success",
            "os": "ubuntu-latest", "python": "3.12",
        }

    def test_manifest_is_normalized_without_network(self):
        result = normalize_github_manifest(self.manifest,
                                           expected_commit=self.sha, expected_run_id="123",
                                           observed_at="2026-11-12T16:00:00Z")
        self.assertEqual(result["environment"], "ubuntu-latest-py3.12")
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["source"], "github_actions")

    def test_rejects_wrong_run_commit_source_and_schema(self):
        for key, value in (
            ("run_id", "999"), ("commit", "b" * 40),
            ("source", "termux_bridge"), ("schema_version", 999),
            ("status", "pending"), ("os", None),
        ):
            with self.subTest(key=key):
                bad = {**self.manifest, key: value}
                with self.assertRaises(ValueError):
                    normalize_github_manifest(bad, expected_commit=self.sha,
                                              expected_run_id="123")

    def test_rejects_unverified_expectations(self):
        with self.assertRaises(ValueError):
            normalize_github_manifest(self.manifest, expected_commit="b" * 40,
                                      expected_run_id="123")


if __name__ == "__main__":
    unittest.main()
