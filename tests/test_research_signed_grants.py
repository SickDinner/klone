from dataclasses import replace
import unittest

from klone.research_signed_grants import (
    issue_research_grant, verify_research_grant,
)


class SignedGrantTests(unittest.TestCase):
    def setUp(self):
        self.key = b"k" * 32
        self.grant = issue_research_grant(
            principal="owner", resource_id="trace-1",
            report_version=2, policy_version=4,
            expires_at=1000, nonce="unique-nonce-value-1", key=self.key)

    def check(self, grant=None, **overrides):
        args = dict(
            grant=self.grant if grant is None else grant,
            principal="owner", resource_id="trace-1",
            report_version=2, policy_version=4, now=999, key=self.key)
        args.update(overrides)
        return verify_research_grant(**args)

    def test_valid_and_expired(self):
        self.assertTrue(self.check())
        self.assertFalse(self.check(now=1000))

    def test_scope_and_policy_rejections(self):
        for changes in (
            {"principal": "other"}, {"resource_id": "trace-2"},
            {"report_version": 3}, {"policy_version": 5},
            {"key": b"x" * 32},
        ):
            with self.subTest(changes=changes):
                self.assertFalse(self.check(**changes))

    def test_forgery_and_malformed_inputs(self):
        for grant in (
            replace(self.grant, principal="attacker"),
            replace(self.grant, expires_at=2000),
            replace(self.grant, signature=None),
            replace(self.grant, signature=42),
            replace(self.grant, report_version=True),
        ):
            with self.subTest(grant=grant):
                self.assertFalse(self.check(grant=grant))

    def test_short_key_rejected(self):
        with self.assertRaises(ValueError):
            self.check(key=b"short")


if __name__ == "__main__":
    unittest.main()
