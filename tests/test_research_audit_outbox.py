import json
import tempfile
from pathlib import Path
from unittest import TestCase

from klone.research_audit_outbox import ResearchAuditOutbox
from klone.research_atomic_run import finalize_verified_run_atomically
from klone.research_run_journal import ResearchRunJournal
from klone.research_source_manifest import manifest_public_source


def inputs(db):
    return dict(
        database_path=db, run_id="r1", trace_id="t1", dossier_id="demo",
        json_text=json.dumps({
            "hypotheses": [{"hypothesis_id": "h", "statement": "Archive claim"}],
            "evidence": [{
                "evidence_id": "e", "source_ref": "archive:1",
                "hypothesis_id": "h", "stance": "supports",
                "quality": "medium", "rationale": "Record",
                "dependency_group": "archive"}]}),
        manifests={"archive:1": manifest_public_source(
            source_id="archive:1", content=b"record")},
        source_bytes={"archive:1": b"record"})


class AuditOutboxTests(TestCase):
    def test_completed_run_creates_durable_event_and_delivers(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "research.sqlite"
            ResearchRunJournal(db).transition(
                run_id="r1", state="started", trace_id="t1", dossier_id="demo")
            finalize_verified_run_atomically(**inputs(db))
            outbox = ResearchAuditOutbox(db)
            pending = outbox.pending()
            self.assertEqual(len(pending), 1)
            self.assertEqual(pending[0].event_id, "research-run:r1")
            received = []
            self.assertEqual(outbox.deliver(sink=received.append), 1)
            self.assertEqual(len(received), 1)
            self.assertEqual(outbox.pending(), ())
            self.assertEqual(outbox.deliver(sink=received.append), 0)

    def test_sink_failure_preserves_pending_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "research.sqlite"
            ResearchRunJournal(db).transition(
                run_id="r1", state="started", trace_id="t1", dossier_id="demo")
            finalize_verified_run_atomically(**inputs(db))
            outbox = ResearchAuditOutbox(db)
            def unavailable(event):
                raise RuntimeError("Audit unavailable")
            with self.assertRaises(RuntimeError):
                outbox.deliver(sink=unavailable)
            self.assertEqual(len(ResearchAuditOutbox(db).pending()), 1)

    def test_enqueue_requires_transaction(self):
        with tempfile.TemporaryDirectory() as tmp:
            import sqlite3
            from contextlib import closing
            db = Path(tmp) / "research.sqlite"
            with closing(sqlite3.connect(db)) as conn:
                ResearchAuditOutbox.initialize(conn)
                conn.commit()
                with self.assertRaises(RuntimeError):
                    ResearchAuditOutbox.enqueue_in_transaction(
                        conn, run_id="r1", trace_id="t", dossier_id="d",
                        dossier_version=1)
