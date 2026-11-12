"""Offline tests for explicit local evidence import."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("evidence_import", ROOT / "tools" / "import_test_evidence.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class EvidenceImportTests(unittest.TestCase):
    def test_valid_import_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "evidence.json"
            db = Path(tmp) / "evidence.sqlite"
            record = {
                "source": "github_actions", "run_id": "1234", "commit": "a" * 40,
                "status": "success", "observed_at": "2026-11-12T16:00:00Z",
                "environment": "ubuntu-3.12",
            }
            path.write_text(json.dumps(record), encoding="utf-8")
            args = ["--database", str(db), "--file", str(path),
                    "--expected-source", "github_actions", "--expected-commit", "a" * 40]
            self.assertEqual(module.main(args), 0)
            self.assertEqual(module.main(args), 0)
            from klone.test_evidence_ledger import EvidenceLedger
            self.assertEqual(len(EvidenceLedger(db).list_for_commit("a" * 40)), 1)

    def test_wrong_commit_fails_before_database_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "evidence.json"
            db = Path(tmp) / "evidence.sqlite"
            path.write_text(json.dumps({
                "source": "termux_bridge", "run_id": "issue-1",
                "commit": "b" * 40, "status": "success",
                "observed_at": "2026-11-12T16:00:00Z",
            }), encoding="utf-8")
            with self.assertRaises(SystemExit):
                module.main(["--database", str(db), "--file", str(path),
                             "--expected-source", "github_actions",
                             "--expected-commit", "a" * 40])
            self.assertFalse(db.exists())

    def test_oversized_file_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "evidence.json"
            path.write_text("x" * (module.MAX_BYTES + 1), encoding="utf-8")
            with self.assertRaises(ValueError):
                module.load_record(path)


if __name__ == "__main__":
    unittest.main()
