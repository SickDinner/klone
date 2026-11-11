import json
import tempfile
from pathlib import Path
from unittest import TestCase

from klone.hypervisor_runtime import HypervisorRuntime
from klone.mission_control_research_service import (
    MissionControlResearchService, ResearchServiceRequest,
)
from klone.research_source_manifest import manifest_public_source


def fixture():
    dossier = json.dumps({
        "hypotheses": [{"hypothesis_id": "h", "statement": "Public historical claim"}],
        "evidence": [{
            "evidence_id": "e", "source_ref": "archive:1",
            "hypothesis_id": "h", "stance": "supports",
            "quality": "medium", "rationale": "Document",
            "dependency_group": "archive"}]})
    return dict(
        json_text=dossier,
        manifests={"archive:1": manifest_public_source(
            source_id="archive:1", content=b"document")},
        source_bytes={"archive:1": b"document"})


class MissionControlServiceTests(TestCase):
    def test_preview_run_inspect_and_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "research.sqlite"
            events = []
            service = MissionControlResearchService(
                database_path=path,
                authenticate=lambda principal, role: principal == "alice" and role == "owner",
                authorize=lambda principal, dossier, action: True,
                audit=lambda status, request, action: events.append((status, action)),
                runtime=HypervisorRuntime())
            req = ResearchServiceRequest("alice", "owner", "trace1", "demo")
            preview = service.preview(request=req, **fixture())
            self.assertEqual(preview.report.verified_source_ids, ("archive:1",))
            self.assertFalse(path.exists())
            result = service.run(request=req, **fixture())
            self.assertEqual(result.change.version, 1)
            inspection = service.inspect(request=req, version=1)
            self.assertIn("Public historical claim", inspection.markdown)
            self.assertEqual(events, [
                ("admitted", "preview"), ("completed", "preview"),
                ("admitted", "run"), ("completed", "run"),
                ("admitted", "inspect"), ("completed", "inspect")])

    def test_denied_identity_and_authorization_do_not_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "research.sqlite"
            for authenticate, authorize in [
                (lambda principal, role: False, lambda p, d, a: True),
                (lambda principal, role: True, lambda p, d, a: False),
            ]:
                service = MissionControlResearchService(
                    database_path=path, authenticate=authenticate,
                    authorize=authorize, audit=lambda *args: None,
                    runtime=HypervisorRuntime())
                with self.assertRaises(PermissionError):
                    service.run(
                        request=ResearchServiceRequest("alice", "owner", "t", "demo"),
                        **fixture())
                self.assertFalse(path.exists())

    def test_admission_audit_failure_prevents_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "research.sqlite"
            def fail_audit(*args):
                raise RuntimeError("Audit unavailable")
            service = MissionControlResearchService(
                database_path=path, authenticate=lambda *args: True,
                authorize=lambda *args: True, audit=fail_audit,
                runtime=HypervisorRuntime())
            with self.assertRaises(RuntimeError):
                service.run(
                    request=ResearchServiceRequest("alice", "owner", "t", "demo"),
                    **fixture())
            self.assertFalse(path.exists())

    def test_invalid_actor_role_denied(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "research.sqlite"
            service = MissionControlResearchService(
                database_path=path, authenticate=lambda *args: True,
                authorize=lambda *args: True, audit=lambda *args: None,
                runtime=HypervisorRuntime())
            with self.assertRaises(PermissionError):
                service.run(
                    request=ResearchServiceRequest("alice", "unknown", "t", "demo"),
                    **fixture())
            self.assertFalse(path.exists())
