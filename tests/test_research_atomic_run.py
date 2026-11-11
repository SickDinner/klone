import json
import tempfile
from contextlib import closing
from pathlib import Path
from unittest import TestCase

from klone.research_atomic_run import finalize_verified_run_atomically
from klone.research_run_journal import ResearchRunJournal
from klone.research_dossier_workflow import read_research_dossier
from klone.research_source_manifest import manifest_public_source


def args(path):
    return dict(
        database_path=path, run_id="run-1", trace_id="trace-1", dossier_id="demo",
        json_text=json.dumps({
            "hypotheses": [{"hypothesis_id": "h", "statement": "Archive claim"}],
            "evidence": [{
                "evidence_id": "e", "source_ref": "archive:1",
                "hypothesis_id": "h", "stance": "supports",
                "quality": "medium", "rationale": "Archive",
                "dependency_group": "archive"}]}),
        manifests={"archive:1": manifest_public_source(
            source_id="archive:1", content=b"record")},
        source_bytes={"archive:1": b"record"})


class AtomicResearchRunTests(TestCase):
    def test_atomic_finalization_and_replay_denial(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "research.sqlite"
            journal = ResearchRunJournal(path)
            journal.transition(run_id="run-1", state="started",
                               trace_id="trace-1", dossier_id="demo")
            result = finalize_verified_run_atomically(**args(path))
            self.assertEqual(result.change.version, 1)
            self.assertEqual([x.state for x in journal.history(run_id="run-1")],
                             ["started", "completed"])
            self.assertEqual(read_research_dossier(
                database_path=path, dossier_id="demo", version=1).fingerprint,
                result.review.fingerprint)
            with self.assertRaises(ValueError):
                finalize_verified_run_atomically(**args(path))
            self.assertEqual(len(journal.history(run_id="run-1")), 2)

    def test_missing_source_does_not_append(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "research.sqlite"
            journal = ResearchRunJournal(path)
            journal.transition(run_id="run-1", state="started",
                               trace_id="trace-1", dossier_id="demo")
            data = args(path)
            data["source_bytes"] = {"archive:1": b"changed"}
            with self.assertRaises(ValueError):
                finalize_verified_run_atomically(**data)
            self.assertEqual([x.state for x in journal.history(run_id="run-1")],
                             ["started"])
            with self.assertRaises(ValueError):
                read_research_dossier(
                    database_path=path, dossier_id="demo", version=1)

    def test_sqlite_terminal_insert_failure_rolls_back_dossier(self):
        with tempfile.TemporaryDirectory() as tmp:
            import sqlite3
            path = Path(tmp) / "research.sqlite"
            journal = ResearchRunJournal(path)
            journal.transition(run_id="run-1", state="started",
                               trace_id="trace-1", dossier_id="demo")
            with closing(sqlite3.connect(path)) as db, db:
                db.execute("""CREATE TRIGGER deny_terminal BEFORE INSERT
                    ON research_run_journal WHEN NEW.state='completed'
                    BEGIN SELECT RAISE(ABORT, 'forced failure'); END""")
            with self.assertRaises(sqlite3.IntegrityError):
                finalize_verified_run_atomically(**args(path))
            self.assertEqual([x.state for x in journal.history(run_id="run-1")],
                             ["started"])
            with self.assertRaises(ValueError):
                read_research_dossier(
                    database_path=path, dossier_id="demo", version=1)

    def test_missing_or_swapped_started_run_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "research.sqlite"
            journal = ResearchRunJournal(path)
            journal.transition(run_id="run-1", state="started",
                               trace_id="trace-1", dossier_id="other")
            with self.assertRaises(ValueError):
                finalize_verified_run_atomically(**args(path))
            self.assertEqual(len(journal.history(run_id="run-1")), 1)
