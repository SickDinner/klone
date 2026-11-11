import json
import tempfile
from pathlib import Path
from unittest import TestCase

from klone.hypervisor_runtime import HypervisorRuntime
from klone.mission_control_research_service import (
    MissionControlResearchService, ResearchServiceRequest)
from klone.mission_control_tracked_research import MissionControlTrackedResearch
from klone.research_audit_outbox import ResearchAuditOutbox
from klone.research_run_journal import ResearchRunJournal
from klone.research_source_manifest import manifest_public_source


def inputs():
    return dict(
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


class AtomicOutboxTrackedServiceTests(TestCase):
    def service(self, db, audit=None):
        return MissionControlResearchService(
            database_path=db,
            authenticate=lambda principal, role: principal == "alice" and role == "owner",
            authorize=lambda principal, dossier, action: True,
            audit=audit or (lambda *args: None),
            runtime=HypervisorRuntime())

    def test_completed_run_has_persistent_outbox(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "research.sqlite"
            tracked = MissionControlTrackedResearch(service=self.service(db))
            req = ResearchServiceRequest("alice", "owner", "t", "demo")
            result = tracked.run(run_id="r1", request=req, **inputs())
            self.assertEqual(result.result.change.version, 1)
            self.assertEqual([e.state for e in result.events], ["started", "completed"])
            self.assertEqual(ResearchAuditOutbox(db).pending()[0].event_id,
                             "research-run:r1")
            with self.assertRaises(ValueError):
                tracked.run(run_id="r1", request=req, **inputs())

    def test_external_audit_failure_preserves_completion_and_outbox(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "research.sqlite"
            def audit(status, request, action):
                if status == "completed":
                    raise RuntimeError("Audit offline")
            tracked = MissionControlTrackedResearch(service=self.service(db, audit))
            req = ResearchServiceRequest("alice", "owner", "t", "demo")
            with self.assertRaises(RuntimeError):
                tracked.run(run_id="r1", request=req, **inputs())
            self.assertEqual([e.state for e in ResearchRunJournal(db).history(
                run_id="r1")], ["started", "completed"])
            outbox = ResearchAuditOutbox(db)
            self.assertEqual(len(outbox.pending()), 1)
            received = []
            self.assertEqual(outbox.deliver(sink=received.append), 1)
            self.assertEqual(len(received), 1)
            self.assertEqual(outbox.pending(), ())
