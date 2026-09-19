from __future__ import annotations

import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from klone.blueprint import SYSTEM_BLUEPRINT  # noqa: E402
from klone.rooms import PERMISSION_LEVELS, room_registry  # noqa: E402
from klone.services import ServiceContainer  # noqa: E402
from klone.repository import KloneRepository  # noqa: E402


class HypervisorRuntimeContractTests(unittest.TestCase):
    def test_exactly_one_shared_hypervisor_role_exists(self) -> None:
        hypervisors = [
            agent
            for agent in SYSTEM_BLUEPRINT.agents
            if agent.id == "hypervisor" and agent.layer == "shared"
        ]
        self.assertEqual(
            len(hypervisors),
            1,
            msg="The control plane must expose exactly one shared hypervisor role.",
        )

    def test_every_room_has_known_supervisor_and_hypervisor_visibility(self) -> None:
        known_agent_ids = {agent.id for agent in SYSTEM_BLUEPRINT.agents}
        known_agent_names = {agent.name.lower() for agent in SYSTEM_BLUEPRINT.agents}

        for room in room_registry.list_rooms():
            normalized_supervisor = room.supervisor.lower().strip()
            supervisor_known = (
                normalized_supervisor in known_agent_ids
                or normalized_supervisor in known_agent_names
                or normalized_supervisor.replace(" ", "-") in known_agent_ids
            )
            self.assertTrue(
                supervisor_known,
                msg=f"{room.id} references unknown supervisor {room.supervisor!r}.",
            )
            self.assertIn(
                "hypervisor",
                room.allowed_agents,
                msg=f"{room.id} must keep hypervisor visible for governed routing.",
            )
            self.assertIn(
                "owner",
                room.allowed_roles,
                msg=f"{room.id} must preserve owner access.",
            )

    def test_room_permissions_reference_only_known_permission_levels(self) -> None:
        known_permissions = {permission.id for permission in PERMISSION_LEVELS}
        self.assertTrue(known_permissions)

        for room in room_registry.list_rooms():
            unknown = sorted(set(room.permissions) - known_permissions)
            self.assertEqual(
                unknown,
                [],
                msg=f"{room.id} references unknown permission levels: {unknown}",
            )

    def test_public_v1_capabilities_remain_read_only(self) -> None:
        repository = KloneRepository(PROJECT_ROOT / ".hypervisor_contract_test.sqlite")
        try:
            repository.initialize()
            services = ServiceContainer.build(repository)
            public_v1 = [
                capability
                for capability in services.public_capabilities()
                if capability.path.startswith("/v1/")
            ]
            self.assertTrue(public_v1)
            self.assertTrue(
                all(capability.read_only for capability in public_v1),
                msg="The current public /v1 seam must remain read-only.",
            )
        finally:
            db_path = repository.db_path
            for suffix in ("", "-wal", "-shm"):
                candidate = Path(str(db_path) + suffix)
                if candidate.exists():
                    candidate.unlink()

    def test_core_control_plane_seams_remain_explicit(self) -> None:
        repository = KloneRepository(PROJECT_ROOT / ".hypervisor_contract_seams.sqlite")
        try:
            repository.initialize()
            services = ServiceContainer.build(repository)
            seam_names = {descriptor.name for descriptor in services.seam_descriptors()}
            required = {"MemoryFacade", "PolicyService", "AuditService", "BlobService"}
            missing = sorted(required - seam_names)
            self.assertEqual(
                missing,
                [],
                msg=f"Hypervisor routing depends on missing core seams: {missing}",
            )
        finally:
            db_path = repository.db_path
            for suffix in ("", "-wal", "-shm"):
                candidate = Path(str(db_path) + suffix)
                if candidate.exists():
                    candidate.unlink()


if __name__ == "__main__":
    unittest.main()
