import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from unittest import TestCase

from klone.mission_control_status_ui import render_research_status
from klone.research_run_journal import ResearchRunJournal
from klone.research_audit_outbox import ResearchAuditOutbox


class MissionControlStatusUITests(TestCase):
    def test_escapes_untrusted_identifiers_and_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "research.sqlite"
            journal = ResearchRunJournal(db)
            journal.transition(run_id="<script>alert(1)</script>",
                               state="started", trace_id="t", dossier_id="d")
            with closing(sqlite3.connect(db)) as conn, conn:
                ResearchAuditOutbox.initialize(conn)
            before = db.stat().st_mtime_ns
            page = render_research_status(database_path=db)
            self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", page)
            self.assertNotIn("<script>", page)
            self.assertIn("Kesken jääneet tutkimusajot (1)", page)
            self.assertEqual(db.stat().st_mtime_ns, before)

    def test_missing_database_not_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "missing.sqlite"
            with self.assertRaises(FileNotFoundError):
                render_research_status(database_path=db)
            self.assertFalse(db.exists())
