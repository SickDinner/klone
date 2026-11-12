"""Offline evidence integrity and fail-closed policy checks."""
from __future__ import annotations

from pathlib import Path
from contextlib import closing
import sqlite3
import tempfile
import unittest

from klone.test_evidence_integrity import assess, audit
from klone.test_evidence_ledger import EvidenceLedger


class EvidenceIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "evidence.sqlite"
        self.ledger = EvidenceLedger(self.db)
        self.ledger.initialize()
        self.old, self.new = "a" * 40, "b" * 40

    def add(self, commit, source, status="success", run="r1"):
        self.ledger.append({
            "source": source, "run_id": run, "commit": commit,
            "status": status, "observed_at": "2026-11-12T18:00:00Z",
            "environment": "android" if source == "termux_bridge" else "linux",
        })

    def test_empty_database_has_stable_digest_but_blocks(self):
        first = audit(self.db)
        self.assertTrue(first["valid"])
        self.assertEqual(first["snapshot_sha256"], "00" * 32)
        self.assertEqual(assess(self.db, self.old, self.new)["decision"], "blocked")

    def test_idempotent_snapshot(self):
        self.add(self.new, "termux_bridge")
        self.assertEqual(audit(self.db)["snapshot_sha256"],
                         audit(self.db)["snapshot_sha256"])

    def test_tampered_payload_detected(self):
        self.add(self.new, "termux_bridge")
        with closing(sqlite3.connect(self.db)) as connection:
            connection.execute("UPDATE test_evidence SET payload_json='{}'")
            connection.commit()
        result = audit(self.db)
        self.assertFalse(result["valid"])
        self.assertEqual(assess(self.db, self.old, self.new)["decision"], "blocked")

    def test_tampered_index_detected(self):
        self.add(self.new, "github_actions")
        with closing(sqlite3.connect(self.db)) as connection:
            connection.execute("UPDATE test_evidence SET status='failure'")
            connection.commit()
        self.assertFalse(audit(self.db)["valid"])

    def test_two_sources_never_auto_approve(self):
        self.add(self.new, "github_actions", run="ci")
        self.add(self.new, "termux_bridge", run="phone")
        result = assess(self.db, self.old, self.new)
        self.assertEqual(result["decision"], "manual_review_required")
        self.assertFalse(result["deployment_approval"])

    def test_regression_blocks(self):
        self.add(self.old, "github_actions", run="ci-old")
        self.add(self.new, "github_actions", status="failure", run="ci-new")
        self.add(self.new, "termux_bridge", run="phone")
        result = assess(self.db, self.old, self.new)
        self.assertIn("detected_regression", result["reasons"])
        self.assertEqual(result["decision"], "blocked")

    def test_missing_database_rejected(self):
        with self.assertRaises(ValueError):
            audit(self.db.parent / "missing.sqlite")
