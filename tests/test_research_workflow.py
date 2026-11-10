from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from klone.hypervisor_dispatch import DispatchDenied
from klone.repository import KloneRepository
from klone.research_workflow import run_local_research


class ResearchWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "documents"
        self.root.mkdir()
        (self.root / "evidence.md").write_text("Ancient DNA chronology.", encoding="utf-8")
        self.db = Path(self.tmp.name) / "audit.sqlite"

    def run_research(self, **overrides):
        args = dict(root=self.root, relative_paths=["evidence.md"],
                    question="DNA", room_id="public-room", actor_role="owner",
                    trace_id="research-e2e", classification_level="public",
                    database_path=self.db)
        args.update(overrides)
        return run_local_research(**args)

    def test_real_sqlite_audit_and_cited_report(self):
        outcome = self.run_research()
        self.assertIn("Ancient DNA chronology.", outcome.report.markdown)
        self.assertIn("sha256=", outcome.report.citations[0])
        self.assertEqual(outcome.audit_event_count, 4)
        events = KloneRepository(self.db).list_audit_events(
            room_id="public-room", target_type="service_seam")
        self.assertEqual(len(events), 4)
        self.assertEqual({e["event_type"] for e in events},
                         {"hypervisor_delegated", "hypervisor_completed"})

    def test_denied_room_does_not_read_files(self):
        with self.assertRaises(DispatchDenied):
            self.run_research(room_id="nonexistent-room")

    def test_missing_file_is_audited(self):
        with self.assertRaises(FileNotFoundError):
            self.run_research(relative_paths=["missing.md"])
        events = KloneRepository(self.db).list_audit_events(room_id="public-room")
        self.assertIn("hypervisor_failed", [e["event_type"] for e in events])


if __name__ == "__main__":
    unittest.main()
