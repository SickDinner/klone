import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from unittest import TestCase

from klone.research_health_cli import research_health
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
            journal.transition(run_id="stuck", state="started",
                               trace_id="t", dossier_id="d")
            before = db.stat().st_mtime_ns
            result = research_health(database_path=db)
            self.assertEqual(result["status"], "attention")
            self.assertEqual(result["stuck_runs"], 1)
            self.assertEqual(db.stat().st_mtime_ns, before)

    def test_missing_database_not_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "missing.sqlite"
            with self.assertRaises(FileNotFoundError):
                research_health(database_path=db)
            self.assertFalse(db.exists())
