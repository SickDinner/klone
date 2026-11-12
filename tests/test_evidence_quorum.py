import unittest

from klone.evidence_quorum import assess


COMMIT = "a" * 40


def record(source, **overrides):
    value = {"source": source, "commit": COMMIT,
             "packet_sha256": "b" * 64, "status": "success"}
    value.update(overrides)
    return value


class EvidenceQuorumTests(unittest.TestCase):
    def test_two_sources_require_manual_review(self):
        result = assess([record("github_actions"), record("termux_bridge")], COMMIT)
        self.assertEqual(result["decision"], "manual_review_required")
        self.assertFalse(result["origin_authenticated"])
        self.assertFalse(result["deployment_approval"])

    def test_missing_termux_blocks(self):
        result = assess([record("github_actions")], COMMIT)
        self.assertEqual(result["decision"], "blocked")

    def test_duplicate_source_blocks(self):
        result = assess([record("github_actions"), record("github_actions"),
                         record("termux_bridge")], COMMIT)
        self.assertEqual(result["decision"], "blocked")

    def test_mismatched_commit_blocks(self):
        result = assess([record("github_actions", commit="c" * 40),
                         record("termux_bridge")], COMMIT)
        self.assertEqual(result["decision"], "blocked")

    def test_failure_blocks(self):
        result = assess([record("github_actions", status="failure"),
                         record("termux_bridge")], COMMIT)
        self.assertEqual(result["decision"], "blocked")

    def test_unexpected_source_blocks(self):
        result = assess([record("github_actions"), record("termux_bridge"),
                         record("untrusted")], COMMIT)
        self.assertEqual(result["decision"], "blocked")

    def test_bad_digest_blocks(self):
        result = assess([record("github_actions", packet_sha256="bad"),
                         record("termux_bridge")], COMMIT)
        self.assertEqual(result["decision"], "blocked")

    def test_claimed_verification_does_not_authenticate(self):
        result = assess([record("github_actions", verified_by_trusted_verifier=True),
                         record("termux_bridge", verified_by_trusted_verifier=True)], COMMIT)
        self.assertFalse(result["origin_authenticated"])


if __name__ == "__main__":
    unittest.main()
