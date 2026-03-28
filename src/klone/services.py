from __future__ import annotations

from dataclasses import dataclass
import json

from .audit import AuditService
from .blueprint import SYSTEM_BLUEPRINT
from .guards import governance_guard_catalog
from .memory import MemoryService
from .repository import KloneRepository
from .rooms import room_registry
from .schemas import BlobMetadataRecord, ModuleCapabilityRecord, PublicCapabilityRecord, ServiceSeamRecord


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
    BLOB_ID_PREFIX = "blob:asset:"
    STORAGE_KIND = "local_filesystem"

    def __init__(self, repository: KloneRepository) -> None:
        self.repository = repository

    def seam_descriptor(self) -> ServiceSeamRecord:
        return ServiceSeamRecord(
            id="blob-service",
            name="BlobService",
            implementation="in_process_local_shell",
            status="local_metadata_shell",
            notes=[
                "Projects the existing governed assets table into a local-first blob metadata shell.",
                "Reuses existing /api/assets and /api/assets/{asset_id} read routes without adding a new /v1 blob route.",
                "No public /v1 blobs upload or /v1/blobs/{blob_id}/meta route exists yet.",
            ],
        )

    def public_capabilities(self) -> list[PublicCapabilityRecord]:
        return [
            PublicCapabilityRecord(
                id="blob.metadata.list",
                name="Blob Metadata List",
                category="blob",
                path="/api/assets",
                methods=["GET"],
                read_only=True,
                room_scoped=True,
                status="available_via_asset_routes",
                description="List local blob metadata through the existing governed asset index.",
                backed_by=["BlobService", "PolicyService"],
            ),
            PublicCapabilityRecord(
                id="blob.metadata.detail",
                name="Blob Metadata Detail",
                category="blob",
                path="/api/assets/{asset_id}",
                methods=["GET"],
                read_only=True,
                room_scoped=True,
                status="available_via_asset_routes",
                description="Read a single local blob metadata record through the existing governed asset detail route.",
                backed_by=["BlobService", "PolicyService"],
            ),
        ]

    @classmethod
    def blob_id_for_asset(cls, asset_id: int) -> str:
        return f"{cls.BLOB_ID_PREFIX}{asset_id}"

    @staticmethod
    def linked_object_id_for_asset(asset_id: int) -> str:
        return f"asset:{asset_id}"

    @classmethod
    def asset_id_from_blob_id(cls, blob_id: str) -> int:
        if not blob_id.startswith(cls.BLOB_ID_PREFIX):
            raise ValueError("Blob id must use the blob:asset:<id> format.")
        asset_id_text = blob_id.removeprefix(cls.BLOB_ID_PREFIX)
        if not asset_id_text.isdigit():
            raise ValueError("Blob id must end with a numeric asset id.")
        return int(asset_id_text)

    def _record_from_asset_row(self, row: dict[str, object]) -> BlobMetadataRecord:
        metadata_json = row.get("metadata_json")
        metadata = json.loads(metadata_json) if isinstance(metadata_json, str) and metadata_json else None
        canonical_asset_id = row.get("canonical_asset_id")
        canonical_blob_id = (
            self.blob_id_for_asset(int(canonical_asset_id))
            if isinstance(canonical_asset_id, int)
            else None
        )
        return BlobMetadataRecord(
            blob_id=self.blob_id_for_asset(int(row["id"])),
            asset_id=int(row["id"]),
            linked_object_id=self.linked_object_id_for_asset(int(row["id"])),
            dataset_id=int(row["dataset_id"]),
            dataset_label=str(row["dataset_label"]),
            room_id=str(row["room_id"]),
            classification_level=str(row["classification_level"]),
            asset_kind=str(row["asset_kind"]),
            media_type=str(row["mime_type"] or "application/octet-stream"),
            storage_kind=self.STORAGE_KIND,
            size_bytes=int(row["size_bytes"]),
            sha256=str(row["sha256"]),
            dedup_status=str(row["dedup_status"]),
            canonical_blob_id=canonical_blob_id,
            file_name=str(row["file_name"]),
            relative_path=str(row["relative_path"]),
            indexed_at=str(row["indexed_at"]),
            metadata=metadata,
        )

    def list_blob_metadata(
        self,
        *,
        room_id: str,
        dataset_id: int | None = None,
        limit: int = 40,
    ) -> list[BlobMetadataRecord]:
        rows = self.repository.list_assets(room_id=room_id, dataset_id=dataset_id, limit=limit)
        return [self._record_from_asset_row(row) for row in rows]

    def get_blob_metadata(
        self,
        *,
        blob_id: str,
        room_id: str,
    ) -> BlobMetadataRecord | None:
        asset_id = self.asset_id_from_blob_id(blob_id)
        row = self.repository.get_asset(asset_id, room_id=room_id)
        if row is None:
            return None
        return self._record_from_asset_row(row)


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
            blob=BlobService(repository),
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
            *self.blob.public_capabilities(),
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
