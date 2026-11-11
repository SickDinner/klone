import json
from unittest import TestCase

from klone.hypervisor_runtime import HypervisorRuntime
from klone.research_mission_gateway import preview_via_mission_control
from klone.research_source_manifest import manifest_public_source


class MissionGatewayTests(TestCase):
    def setUp(self):
        self.args = dict(
            runtime=HypervisorRuntime(), actor_role="owner",
            trace_id="mission-preview-1",
            authenticate_actor=lambda role: role == "owner",
            json_text=json.dumps({
                "hypotheses": [{"hypothesis_id": "h", "statement": "Claim"}],
                "evidence": [{
                    "evidence_id": "e", "source_ref": "archive:1",
                    "hypothesis_id": "h", "stance": "supports",
                    "quality": "medium", "rationale": "Document",
                    "dependency_group": "archive"}]}),
            manifests={"archive:1": manifest_public_source(
                source_id="archive:1", content=b"document")},
            source_bytes={"archive:1": b"document"})

    def test_authenticated_hypervisor_preview(self):
        decision, result = preview_via_mission_control(**self.args)
        self.assertEqual(decision.decision, "allowed")
        self.assertEqual(decision.permission, "read")
        self.assertEqual(result.report.verified_source_ids, ("archive:1",))

    def test_unauthenticated_rejected(self):
        with self.assertRaises(PermissionError):
            preview_via_mission_control(**dict(
                self.args, authenticate_actor=lambda role: False))

    def test_bad_source_rejected(self):
        with self.assertRaises(ValueError):
            preview_via_mission_control(**dict(
                self.args, source_bytes={"archive:1": b"changed"}))

    def test_bad_role_rejected(self):
        with self.assertRaises(PermissionError):
            preview_via_mission_control(**dict(
                self.args, actor_role="unknown",
                authenticate_actor=lambda role: True))
