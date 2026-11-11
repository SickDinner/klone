import sqlite3
import json
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch
import tempfile
from contextlib import closing
from pathlib import Path
from unittest import TestCase

from klone.research_health_cli import research_health, main
from klone.research_run_journal import ResearchRunJournal
from klone.research_audit_outbox import ResearchAuditOutbox
from klone.research_dossier_store import DossierStore


class ResearchHealthCLITests(TestCase):
    def test_clean_and_stuck_status_without_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "health.sqlite"
            journal = ResearchRunJournal(db)
            with closing(sqlite3.connect(db)) as conn, conn:
                ResearchAuditOutbox.initialize(conn)
                DossierStore(db)._initialize(conn)
            self.assertEqual(research_health(database_path=db)["status"], "ok")
            self.assertEqual(research_health(database_path=db)["issue_codes"], [])
            journal.transition(run_id="stuck", state="started",
                               trace_id="t", dossier_id="d")
            before = db.stat().st_mtime_ns
            result = research_health(database_path=db)
            self.assertEqual(result["status"], "attention")
            self.assertEqual(result["stuck_runs"], 1)
            self.assertEqual(result["issue_codes"], ["stuck_runs"])
            self.assertEqual(db.stat().st_mtime_ns, before)

    def test_missing_database_not_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "missing.sqlite"
            with self.assertRaises(FileNotFoundError):
                research_health(database_path=db)
            self.assertFalse(db.exists())

    def test_corrupt_database_fails_closed_with_machine_readable_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "corrupt.sqlite"
            payload = b"not a sqlite database"
            db.write_bytes(payload)
            output = StringIO()
            with patch("sys.argv", ["klone-research-health", "--database", str(db)]):
                with redirect_stdout(output):
                    exit_code = main()
            self.assertEqual(exit_code, 2)
            self.assertEqual(json.loads(output.getvalue()), {
                "status": "error", "reason": "DatabaseError"
            })
            self.assertEqual(db.read_bytes(), payload)

    def test_missing_database_cli_returns_error_without_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "missing.sqlite"
            output = StringIO()
            with patch("sys.argv", ["klone-research-health", "--database", str(db)]):
                with redirect_stdout(output):
                    exit_code = main()
            self.assertEqual(exit_code, 2)
            self.assertEqual(json.loads(output.getvalue()), {
                "status": "error", "reason": "FileNotFoundError"
            })
            self.assertFalse(db.exists())

    def test_pending_delivery_does_not_mask_integrity_attention(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "health.sqlite"
            journal = ResearchRunJournal(db)
            with closing(sqlite3.connect(db)) as conn, conn:
                ResearchAuditOutbox.initialize(conn)
                DossierStore(db)._initialize(conn)
            journal.transition(run_id="unfinished", state="started",
                               trace_id="trace", dossier_id="dossier")
            result = research_health(database_path=db)
            self.assertEqual(result["status"], "attention")
            self.assertEqual(result["stuck_runs"], 1)
            self.assertIn("pending_audit_delivery", result)
