from __future__ import annotations

from dataclasses import dataclass

from .audit import AuditService
from .blueprint import SYSTEM_BLUEPRINT
from .guards import governance_guard_catalog
from .memory import MemoryService
from .repository import KloneRepository
from .rooms import room_registry
from .schemas import ModuleCapabilityRecord, PublicCapabilityRecord, ServiceSeamRecord


def module_registry_payload() -> list[ModuleCapabilityRecord]:
    return [
        ModuleCapabilityRecord(
            id=module.id,
            name=module.name,
            stage=module.stage,
            status=module.status,
            supervisor=module.supervisor,
            key_inputs=list(module.key_inputs),
            outputs=list(module.outputs),
            capability_count=len(module.key_inputs) + len(module.outputs),
        )
        for module in SYSTEM_BLUEPRINT.modules
    ]


class MemoryFacade:
    def __init__(self, repository: KloneRepository) -> None:
        self.memory_service = MemoryService(repository)

    def seam_descriptor(self) -> ServiceSeamRecord:
        return ServiceSeamRecord(
            id="memory-facade",
            name="MemoryFacade",
            implementation="in_process",
            status="active",
            notes=[
                "Wraps the existing read-only memory retrieval and context assembly surfaces.",
                "Does not introduce write authority or semantic retrieval.",
            ],
        )

    def public_capabilities(self) -> list[PublicCapabilityRecord]:
        return [
            PublicCapabilityRecord(
                id="memory.events.read",
                name="Memory Events",
                category="memory",
                path="/api/memory/events",
                methods=["GET"],
                read_only=True,
                room_scoped=True,
                status="available",
                description="List room-scoped memory events with deterministic filtering.",
                backed_by=["MemoryFacade"],
            ),
            PublicCapabilityRecord(
                id="memory.episodes.read",
                name="Memory Episodes",
                category="memory",
                path="/api/memory/episodes",
                methods=["GET"],
                read_only=True,
                room_scoped=True,
                status="available",
                description="List room-scoped memory episodes with deterministic filtering.",
                backed_by=["MemoryFacade"],
            ),
            PublicCapabilityRecord(
                id="memory.context.package",
                name="Memory Context Package",
                category="memory_context",
                path="/api/memory/context/package",
                methods=["GET"],
                read_only=True,
                room_scoped=True,
                status="available",
                description="Assemble a bounded, source-linked context package for one event or episode.",
                backed_by=["MemoryFacade"],
            ),
            PublicCapabilityRecord(
                id="memory.context.payload",
                name="Read-Only Context Payload",
                category="memory_context",
                path="/api/memory/context/payload",
                methods=["GET"],
                read_only=True,
                room_scoped=True,
                status="available",
                description="Expose exact included/excluded context for a bounded read-only memory scope.",
                backed_by=["MemoryFacade"],
            ),
            PublicCapabilityRecord(
                id="memory.context.answer",
                name="Bounded Read-Only Answer",
                category="memory_context",
                path="/api/memory/context/answer",
                methods=["GET"],
                read_only=True,
                room_scoped=True,
                status="available",
                description="Generate a bounded source-linked answer without enabling memory mutation.",
                backed_by=["MemoryFacade"],
            ),
        ]


class PolicyService:
    def seam_descriptor(self) -> ServiceSeamRecord:
        return ServiceSeamRecord(
            id="policy-service",
            name="PolicyService",
            implementation="in_process",
            status="active",
            notes=[
                "Wraps room registry and deterministic governance guard visibility.",
                "Acts as the current control-plane policy seam.",
            ],
        )

    def public_capabilities(self) -> list[PublicCapabilityRecord]:
        room_count = len(room_registry.list_rooms())
        guard_count = len(governance_guard_catalog())
        return [
            PublicCapabilityRecord(
                id="control.status.read",
                name="Mission Control Status",
                category="control_plane",
                path="/api/status",
                methods=["GET"],
                read_only=True,
                room_scoped=False,
                status="available",
                description="Read the current mission-control aggregate state.",
                backed_by=["PolicyService", "AuditService"],
            ),
            PublicCapabilityRecord(
                id="policy.rooms.read",
                name="Room Registry",
                category="policy",
                path="/api/rooms",
                methods=["GET"],
                read_only=True,
                room_scoped=False,
                status=f"available:{room_count}_rooms",
                description="Inspect the governed room registry and supervisor assignments.",
                backed_by=["PolicyService"],
            ),
            PublicCapabilityRecord(
                id="policy.guards.read",
                name="Governance Guards",
                category="policy",
                path="/api/governance/guards",
                methods=["GET"],
                read_only=True,
                room_scoped=False,
                status=f"available:{guard_count}_guards",
                description="Read deterministic guard visibility for access, classification, audit, and output.",
                backed_by=["PolicyService"],
            ),
        ]


class BlobService:
    def seam_descriptor(self) -> ServiceSeamRecord:
        return ServiceSeamRecord(
            id="blob-service",
            name="BlobService",
            implementation="in_process_placeholder",
            status="placeholder",
            notes=[
                "No public blob route is exposed in A1.1.",
                "This seam exists only to keep the future object/blob contract boundary explicit.",
            ],
        )


@dataclass(frozen=True)
class ServiceContainer:
    memory: MemoryFacade
    policy: PolicyService
    audit: AuditService
    blob: BlobService

    @classmethod
    def build(cls, repository: KloneRepository) -> "ServiceContainer":
        return cls(
            memory=MemoryFacade(repository),
            policy=PolicyService(),
            audit=AuditService(repository),
            blob=BlobService(),
        )

    def seam_descriptors(self) -> list[ServiceSeamRecord]:
        return [
            self.memory.seam_descriptor(),
            self.policy.seam_descriptor(),
            ServiceSeamRecord(
                id="audit-service",
                name="AuditService",
                implementation="in_process",
                status="active",
                notes=[
                    "Reuses the append-only deterministic audit pipeline already in the monolith.",
                    "No new write authority is exposed through /v1 in A1.1.",
                ],
            ),
            self.blob.seam_descriptor(),
        ]

    def public_capabilities(self) -> list[PublicCapabilityRecord]:
        return [
            PublicCapabilityRecord(
                id="v1.capabilities.read",
                name="V1 Capabilities",
                category="control_plane",
                path="/v1/capabilities",
                methods=["GET"],
                read_only=True,
                room_scoped=False,
                status="available",
                description="Read the currently exposed public control-plane seam and service boundaries.",
                backed_by=["PolicyService", "AuditService"],
            ),
            *self.policy.public_capabilities(),
            *self.memory.public_capabilities(),
            PublicCapabilityRecord(
                id="audit.preview.read",
                name="Audit Preview",
                category="audit",
                path="/api/audit",
                methods=["GET"],
                read_only=True,
                room_scoped=True,
                status="available",
                description="Read bounded audit preview rows through the existing governed API.",
                backed_by=["AuditService", "PolicyService"],
            ),
        ]

