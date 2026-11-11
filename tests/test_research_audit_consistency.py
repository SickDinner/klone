import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from unittest import TestCase

from klone.research_audit_consistency import inspect_audit_consistency
from klone.research_audit_outbox import ResearchAuditOutbox
from klone.research_run_journal import ResearchRunJournal
from klone.research_dossier_store import DossierStore


class AuditConsistencyTests(TestCase):
    def test_missing_database_is_not_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "missing.sqlite"
            with self.assertRaises(FileNotFoundError):
                inspect_audit_consistency(database_path=path)
            self.assertFalse(path.exists())

    def test_detects_orphaned_and_mismatched_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "research.sqlite"
            journal = ResearchRunJournal(path)
            journal.transition(run_id="r1", state="started",
                               trace_id="t", dossier_id="d")
            journal.transition(run_id="r1", state="completed",
                               trace_id="t", dossier_id="d")
            with closing(sqlite3.connect(path)) as db, db:
                DossierStore(path)._initialize(db)
                ResearchAuditOutbox.initialize(db)
                db.execute("INSERT INTO research_audit_outbox "
                           "(event_id,run_id,trace_id,dossier_id,dossier_version) "
                           "VALUES (?,?,?,?,?)", ("bad", "orphan", "t", "d", 99))
            before = path.stat().st_mtime_ns
            result = inspect_audit_consistency(database_path=path)
            self.assertFalse(result.healthy)
            self.assertEqual(result.completed_missing_snapshot, ("r1",))
            self.assertEqual(result.outbox_missing_completed, ("bad",))
            self.assertEqual(result.outbox_version_mismatch, ("bad",))
            self.assertEqual(result.malformed_event_ids, ("bad",))
            self.assertEqual(path.stat().st_mtime_ns, before)

    def test_incomplete_schema_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "research.sqlite"
            ResearchRunJournal(path).transition(
                run_id="r", state="started", trace_id="t", dossier_id="d")
            with self.assertRaises(ValueError):
                inspect_audit_consistency(database_path=path)
