import tempfile
from pathlib import Path
from unittest import TestCase

from klone.research_run_journal import ResearchRunJournal


class ResearchRunJournalTests(TestCase):
    def test_persistent_ordered_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "journal.sqlite"
            journal = ResearchRunJournal(path)
            first = journal.transition(
                run_id="r1", state="started", trace_id="t", dossier_id="d")
            second = journal.transition(
                run_id="r1", state="completed", trace_id="t",
                dossier_id="d", detail="version 1")
            self.assertEqual((first.sequence, second.sequence), (1, 2))
            history = ResearchRunJournal(path).history(run_id="r1")
            self.assertEqual(tuple(x.state for x in history), ("started", "completed"))
            self.assertEqual(history[-1].detail, "version 1")

    def test_rejects_invalid_transitions_and_identity_swap(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = ResearchRunJournal(Path(tmp) / "journal.sqlite")
            with self.assertRaises(ValueError):
                journal.transition(run_id="r1", state="completed",
                                   trace_id="t", dossier_id="d")
            journal.transition(run_id="r1", state="started",
                               trace_id="t", dossier_id="d")
            with self.assertRaises(ValueError):
                journal.transition(run_id="r1", state="started",
                                   trace_id="t", dossier_id="d")
            with self.assertRaises(ValueError):
                journal.transition(run_id="r1", state="failed",
                                   trace_id="other", dossier_id="d")
            journal.transition(run_id="r1", state="failed",
                               trace_id="t", dossier_id="d")
            with self.assertRaises(ValueError):
                journal.transition(run_id="r1", state="completed",
                                   trace_id="t", dossier_id="d")
            self.assertEqual(len(journal.history(run_id="r1")), 2)

    def test_independent_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = ResearchRunJournal(Path(tmp) / "journal.sqlite")
            for run in ("a", "b"):
                journal.transition(run_id=run, state="started",
                                   trace_id=run, dossier_id="d")
            self.assertEqual(len(journal.history(run_id="a")), 1)
            self.assertEqual(len(journal.history(run_id="b")), 1)
