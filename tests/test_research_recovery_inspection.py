import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from unittest import TestCase

from klone.research_recovery_inspection import inspect_research_recovery
from klone.research_run_journal import ResearchRunJournal
from klone.research_audit_outbox import ResearchAuditOutbox


class ResearchRecoveryInspectionTests(TestCase):
    def test_missing_db_not_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "missing.sqlite"
            with self.assertRaises(FileNotFoundError):
                inspect_research_recovery(database_path=db)
            self.assertFalse(db.exists())

    def test_detects_started_pending_and_legacy_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "research.sqlite"
            journal = ResearchRunJournal(db)
            journal.transition(run_id="stuck", state="started",
                               trace_id="t", dossier_id="d")
            journal.transition(run_id="legacy", state="started",
                               trace_id="t", dossier_id="d")
            journal.transition(run_id="legacy", state="completed",
                               trace_id="t", dossier_id="d")
            with closing(sqlite3.connect(db)) as conn, conn:
                ResearchAuditOutbox.initialize(conn)
                conn.execute("INSERT INTO research_audit_outbox "
                             "(event_id,run_id,trace_id,dossier_id,dossier_version) "
                             "VALUES (?,?,?,?,?)",
                             ("research-run:other", "other", "t", "d", 1))
            before = db.stat().st_mtime_ns
            result = inspect_research_recovery(database_path=db)
            self.assertEqual(result.started_without_terminal, ("stuck",))
            self.assertEqual(result.completed_without_outbox, ("legacy",))
            self.assertEqual(result.pending_audit_delivery, ("research-run:other",))
            self.assertEqual(db.stat().st_mtime_ns, before)

    def test_incomplete_schema_is_rejected_without_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "research.sqlite"
            ResearchRunJournal(db).transition(
                run_id="r", state="started", trace_id="t", dossier_id="d")
            with self.assertRaises(ValueError):
                inspect_research_recovery(database_path=db)
