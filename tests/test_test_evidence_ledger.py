"""Offline contract tests for source-separated test evidence history."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from klone.test_evidence_ledger import EvidenceLedger, validate


def evidence(source="github_actions", run_id="run-1", status="success"):
    return {
        "source": source,
        "run_id": run_id,
        "commit": "a" * 40,
        "status": status,
        "observed_at": "2026-11-12T15:00:00Z",
        "environment": "ubuntu-python3.12" if source == "github_actions" else "android-termux",
    }


class EvidenceLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = EvidenceLedger(Path(self.tmp.name) / "evidence.sqlite")
        self.ledger.initialize()

    def tearDown(self):
        self.tmp.cleanup()

    def test_deduplication_is_deterministic(self):
        first, inserted = self.ledger.append(evidence())
        second, repeated = self.ledger.append(evidence())
        self.assertEqual(first, second)
        self.assertTrue(inserted)
        self.assertFalse(repeated)
        self.assertEqual(len(self.ledger.list_for_commit("a" * 40)), 1)

    def test_sources_remain_separate_and_require_review(self):
        self.ledger.append(evidence())
        self.assertEqual(self.ledger.compare("a" * 40)["review_state"], "pending_evidence")
        self.ledger.append(evidence(source="termux_bridge", run_id="issue-105"))
        result = self.ledger.compare("a" * 40)
        self.assertEqual(result["sources"]["github_actions"]["count"], 1)
        self.assertEqual(result["sources"]["termux_bridge"]["count"], 1)
        self.assertEqual(result["review_state"], "manual_review_required")

    def test_rejects_untrusted_shapes_and_credentials(self):
        for bad in (
            {**evidence(), "source": "user_claim"},
            {**evidence(), "status": "approved"},
            {**evidence(), "commit": "not-a-sha"},
            {**evidence(), "observed_at": "2026-11-12T15:00:00"},
            {**evidence(), "token": "secret"},
            {**evidence(), "details": {"payload": "x" * 10000}},
        ):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    validate(bad)
        self.assertEqual(self.ledger.list_for_commit("a" * 40), [])

    def test_different_statuses_are_distinct_observations(self):
        self.ledger.append(evidence(status="failure"))
        self.ledger.append(evidence(status="success"))
        self.assertEqual(len(self.ledger.list_for_commit("a" * 40)), 2)
        self.assertEqual(
            self.ledger.compare("a" * 40)["sources"]["github_actions"]["statuses"],
            ["failure", "success"],
        )


if __name__ == "__main__":
    unittest.main()
