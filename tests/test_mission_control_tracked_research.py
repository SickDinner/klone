import json
import tempfile
from pathlib import Path
from unittest import TestCase

from klone.hypervisor_runtime import HypervisorRuntime
from klone.mission_control_research_service import (
    MissionControlResearchService, ResearchServiceRequest)
from klone.mission_control_tracked_research import MissionControlTrackedResearch
from klone.research_source_manifest import manifest_public_source
from klone.research_run_journal import ResearchRunJournal


def inputs():
    return dict(
        json_text=json.dumps({
            "hypotheses": [{"hypothesis_id": "h", "statement": "Public historical claim"}],
            "evidence": [{
                "evidence_id": "e", "source_ref": "archive:1",
                "hypothesis_id": "h", "stance": "supports",
                "quality": "medium", "rationale": "Document",
                "dependency_group": "archive"}]}),
        manifests={"archive:1": manifest_public_source(
            source_id="archive:1", content=b"document")},
        source_bytes={"archive:1": b"document"})


class TrackedResearchTests(TestCase):
    def make_service(self, path, *, authorized=True):
        return MissionControlResearchService(
            database_path=path,
            authenticate=lambda principal, role: principal == "alice" and role == "owner",
            authorize=lambda principal, dossier, action: authorized,
            audit=lambda *args: None,
            runtime=HypervisorRuntime())

    def test_run_and_persistent_history_and_no_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "research.sqlite"
            service = self.make_service(db)
            tracked = MissionControlTrackedResearch(service=service)
            req = ResearchServiceRequest("alice", "owner", "trace-1", "demo")
            result = tracked.run(run_id="run-1", request=req, **inputs())
            self.assertEqual(result.result.change.version, 1)
            self.assertEqual([e.state for e in result.events], ["started", "completed"])
            self.assertEqual([e.state for e in ResearchRunJournal(db).history(
                run_id="run-1")], ["started", "completed"])
            with self.assertRaises(ValueError):
                tracked.run(run_id="run-1", request=req, **inputs())
            self.assertEqual(tracked.history(run_id="run-1", request=req), result.events)

    def test_denied_request_never_starts_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "research.sqlite"
            tracked = MissionControlTrackedResearch(
                service=self.make_service(db, authorized=False))
            with self.assertRaises(PermissionError):
                tracked.run(
                    run_id="run-1",
                    request=ResearchServiceRequest("alice", "owner", "t", "demo"),
                    **inputs())
            self.assertFalse(db.exists())

    def test_invalid_sources_fail_and_record_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "research.sqlite"
            tracked = MissionControlTrackedResearch(service=self.make_service(db))
            req = ResearchServiceRequest("alice", "owner", "t", "demo")
            args = inputs()
            args["source_bytes"] = {"archive:1": b"changed"}
            with self.assertRaises(ValueError):
                tracked.run(run_id="run-1", request=req, **args)
            self.assertEqual(
                [e.state for e in tracked.history(run_id="run-1", request=req)],
                ["started", "failed"])
            with self.assertRaises(ValueError):
                tracked.run(run_id="run-1", request=req, **inputs())

    def test_history_is_dossier_scoped(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "research.sqlite"
            tracked = MissionControlTrackedResearch(service=self.make_service(db))
            req = ResearchServiceRequest("alice", "owner", "t", "demo")
            tracked.run(run_id="run-1", request=req, **inputs())
            other = ResearchServiceRequest("alice", "owner", "t", "other")
            with self.assertRaises(PermissionError):
                tracked.history(run_id="run-1", request=other)
