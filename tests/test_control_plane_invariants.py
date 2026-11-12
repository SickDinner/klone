"""Cross-cutting fail-closed regression matrix for KLONE control plane."""
from __future__ import annotations

import sys
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from klone.blueprint import SYSTEM_BLUEPRINT
from klone.hypervisor_dispatch import DispatchDenied
from klone.hypervisor_runtime import HypervisorRuntime
from klone.hypervisor_safe_pipeline import SafeReadPipeline
from klone.repository import KloneRepository
from klone.rooms import PERMISSION_LEVELS, room_registry
from klone.services import ServiceContainer


class ControlPlaneInvariantTests(unittest.TestCase):
    def test_all_rooms_preserve_owner_and_known_permissions(self):
        permissions = {p.id for p in PERMISSION_LEVELS}
        agents = {a.id for a in SYSTEM_BLUEPRINT.agents}
        rooms = room_registry.list_rooms()
        self.assertTrue(rooms)
        for room in rooms:
            with self.subTest(room=room.id):
                self.assertIn("owner", room.allowed_roles)
                self.assertIn("hypervisor", room.allowed_agents)
                self.assertFalse(set(room.permissions) - permissions)
                self.assertFalse(set(room.allowed_agents) - agents)

    def test_public_api_capabilities_never_expose_mutations(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = KloneRepository(Path(folder) / "contracts.sqlite")
            repo.initialize()
            capabilities = ServiceContainer.build(repo).public_capabilities()
            public = [c for c in capabilities if c.path.startswith("/v1/")]
            self.assertTrue(public)
            for capability in public:
                with self.subTest(path=capability.path):
                    self.assertTrue(capability.read_only)

    def test_denied_routes_and_failed_audit_never_read_memory(self):
        called = []
        events = []
        pipeline = SafeReadPipeline(
            runtime=HypervisorRuntime(),
            handlers={"MemoryFacade": lambda room: called.append(room) or {"secret": "no"}},
            audit=lambda event, route, seam: events.append(event),
            authorize_output=lambda classification: "allowed" if classification == "public" else "summary_only",
        )
        cases = (
            {"seam": "unknown"},
            {"classification_level": "intimate"},
            {"room_id": "restricted-room", "classification_level": "personal"},
        )
        for changes in cases:
            with self.subTest(changes=changes):
                params = dict(seam="MemoryFacade", room_id="public-room", actor_role="owner",
                              trace_id="matrix-denied", classification_level="public")
                params.update(changes)
                with self.assertRaises(DispatchDenied):
                    pipeline.read(**params)
                self.assertEqual(called, [])

        def failed_audit(*args):
            raise OSError("audit storage unavailable")

        audit_pipeline = SafeReadPipeline(
            runtime=HypervisorRuntime(),
            handlers={"MemoryFacade": lambda room: called.append(room)},
            audit=failed_audit,
            authorize_output=lambda _: "allowed",
        )
        with self.assertRaises(OSError):
            audit_pipeline.read(seam="MemoryFacade", room_id="public-room",
                                actor_role="owner", trace_id="matrix-audit",
                                classification_level="public")
        self.assertEqual(called, [])


if __name__ == "__main__":
    unittest.main()
