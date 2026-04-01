from __future__ import annotations

from dataclasses import dataclass
import json

from .art import ArtLabService
from .audit import AuditService
from .blueprint import SYSTEM_BLUEPRINT
from .constitution import ConstitutionService
from .dialogue import DialogueCorpusService
from .guards import governance_guard_catalog, output_guard
from .memory import MemoryService
from .repository import KloneRepository
from .rooms import room_registry
from .schemas import (
    BlobMetadataRecord,
    ModuleCapabilityRecord,
    ObjectEnvelopeRecord,
    PublicCapabilityRecord,
    ServiceSeamRecord,
)
from .simulation import HybridMemoryBoardService


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


def _decode_service_metadata_row(row: dict[str, object]) -> dict[str, object]:
    payload = dict(row)
    metadata_json = payload.pop("metadata_json", None)
    if isinstance(metadata_json, str) and metadata_json:
        payload["metadata"] = json.loads(metadata_json)
    return payload


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
            PublicCapabilityRecord(
                id="v1.query.read",
                name="V1 Room Query",
                category="query",
                path="/v1/rooms/{room_id}/query",
                methods=["POST"],
                read_only=True,
                room_scoped=True,
                status="available",
                description="Run deterministic room-scoped memory event, episode, or audit preview queries through the versioned public control-plane seam.",
                backed_by=["MemoryFacade", "PolicyService", "AuditService"],
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


class SimulationService:
    def __init__(self, repository: KloneRepository) -> None:
        self.hybrid_board = HybridMemoryBoardService(repository)

    def seam_descriptor(self) -> ServiceSeamRecord:
        return ServiceSeamRecord(
            id="simulation-service",
            name="SimulationService",
            implementation="in_process_read_only_projection",
            status="active_projection",
            notes=[
                "Projects governed audit and memory records into a read-only hybrid board surface.",
                "Does not create a second source of truth and does not enable simulation writes.",
            ],
        )

    def public_capabilities(self) -> list[PublicCapabilityRecord]:
        return [
            PublicCapabilityRecord(
                id="simulation.hybrid_board.read",
                name="Hybrid Memory Board",
                category="simulation",
                path="/api/simulation/hybrid-board",
                methods=["GET"],
                read_only=True,
                room_scoped=True,
                status="available",
                description="Read a governed 8x8 hybrid board projected from audit, memory event, and episode surfaces.",
                backed_by=["SimulationService", "MemoryFacade", "AuditService", "PolicyService"],
            )
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
                "Reuses existing /api/assets and /api/assets/{asset_id} read routes and backs GET /v1/rooms/{room_id}/blobs/{blob_id}/meta.",
                "No public /v1 blobs upload route exists yet.",
            ],
        )

    def public_capabilities(self) -> list[PublicCapabilityRecord]:
        return [
            PublicCapabilityRecord(
                id="v1.blobs.meta.read",
                name="V1 Room Blob Metadata",
                category="blob",
                path="/v1/rooms/{room_id}/blobs/{blob_id}/meta",
                methods=["GET"],
                read_only=True,
                room_scoped=True,
                status="available",
                description="Read one room-scoped blob metadata record through the versioned public control-plane seam.",
                backed_by=["BlobService", "PolicyService", "AuditService"],
            ),
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
        if output_guard.evaluate(classification_level=str(row["classification_level"])).decision == "summary_only":
            metadata = {"policy": "summary_only"}
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


class _ObjectEnvelopeProjector:
    VERSION = 1
    SUPPORTED_OBJECT_KINDS = ("dataset", "asset", "memory_event", "memory_episode")

    def __init__(self, repository: KloneRepository) -> None:
        self.repository = repository
        self.memory_service = MemoryService(repository)

    def seam_descriptor(self) -> ServiceSeamRecord:
        return ServiceSeamRecord(
            id="object-envelope-service",
            name="ObjectEnvelopeService",
            implementation="in_process_local_shell",
            status="local_envelope_shell",
            notes=[
                "Projects existing governed dataset, asset, memory event, and memory episode reads into a deterministic local object envelope shell.",
                "Reuses existing read routes plus the public read-only object-get seam without adding write authority.",
            ],
        )

    def public_capabilities(self) -> list[PublicCapabilityRecord]:
        return [
            PublicCapabilityRecord(
                id="v1.objects.get",
                name="V1 Room Object Get",
                category="object",
                path="/v1/rooms/{room_id}/objects/get",
                methods=["POST"],
                read_only=True,
                room_scoped=True,
                status="available",
                description="Read one room-scoped object envelope through the versioned public control-plane seam.",
                backed_by=["ObjectEnvelopeService", "PolicyService", "AuditService"],
            ),
            PublicCapabilityRecord(
                id="object.envelope.dataset",
                name="Dataset Object Envelope",
                category="object",
                path="/api/datasets",
                methods=["GET"],
                read_only=True,
                room_scoped=True,
                status="available_via_existing_read_routes",
                description="Project governed dataset rows into the local object envelope shell.",
                backed_by=["PolicyService"],
            ),
            PublicCapabilityRecord(
                id="object.envelope.asset",
                name="Asset Object Envelope",
                category="object",
                path="/api/assets",
                methods=["GET"],
                read_only=True,
                room_scoped=True,
                status="available_via_existing_read_routes",
                description="Project governed asset rows into the local object envelope shell.",
                backed_by=["BlobService", "PolicyService"],
            ),
            PublicCapabilityRecord(
                id="object.envelope.memory_event",
                name="Memory Event Object Envelope",
                category="object",
                path="/api/memory/events",
                methods=["GET"],
                read_only=True,
                room_scoped=True,
                status="available_via_existing_read_routes",
                description="Project governed memory event rows into the local object envelope shell.",
                backed_by=["MemoryFacade"],
            ),
            PublicCapabilityRecord(
                id="object.envelope.memory_episode",
                name="Memory Episode Object Envelope",
                category="object",
                path="/api/memory/episodes",
                methods=["GET"],
                read_only=True,
                room_scoped=True,
                status="available_via_existing_read_routes",
                description="Project governed memory episode rows into the local object envelope shell.",
                backed_by=["MemoryFacade"],
            ),
        ]

    def list_dataset_envelopes(self, *, room_id: str) -> list[ObjectEnvelopeRecord]:
        rows = self.repository.list_datasets(room_id=room_id)
        return [
            self._build_object_envelope(
                object_id=f"dataset:{row['id']}",
                object_kind="dataset",
                room_id=str(row["room_id"]),
                classification_level=str(row["classification_level"]),
                summary=str(row["label"]),
                backing_routes=["/api/datasets"],
                record=dict(row),
            )
            for row in rows
        ]

    def list_asset_envelopes(
        self,
        *,
        room_id: str,
        dataset_id: int | None = None,
        limit: int = 40,
    ) -> list[ObjectEnvelopeRecord]:
        rows = self.repository.list_assets(room_id=room_id, dataset_id=dataset_id, limit=limit)
        return [
            self._build_object_envelope(
                object_id=f"asset:{row['id']}",
                object_kind="asset",
                room_id=str(row["room_id"]),
                classification_level=str(row["classification_level"]),
                summary=str(row["relative_path"]),
                backing_routes=["/api/assets", "/api/assets/{asset_id}"],
                record=_decode_service_metadata_row(dict(row)),
            )
            for row in rows
        ]

    def list_memory_event_envelopes(
        self,
        *,
        room_id: str,
        limit: int = 40,
        offset: int = 0,
        include_corrected: bool = True,
    ) -> list[ObjectEnvelopeRecord]:
        listing_rows = self.memory_service.query_events(
            room_id=room_id,
            limit=limit,
            offset=offset,
            include_corrected=include_corrected,
        )
        envelopes: list[ObjectEnvelopeRecord] = []
        for row in listing_rows:
            detail_payload = self.memory_service.get_event_detail(room_id=room_id, event_id=int(row["id"]))
            if detail_payload is None:
                continue
            envelopes.append(
                self._build_object_envelope(
                    object_id=f"memory_event:{row['id']}",
                    object_kind="memory_event",
                    room_id=str(row["room_id"]),
                    classification_level=str(row["classification_level"]),
                    summary=str(row["title"]),
                    backing_routes=["/api/memory/events", "/api/memory/events/{event_id}"],
                    record=dict(detail_payload),
                )
            )
        return envelopes

    def list_memory_episode_envelopes(
        self,
        *,
        room_id: str,
        limit: int = 40,
        offset: int = 0,
        include_corrected: bool = True,
    ) -> list[ObjectEnvelopeRecord]:
        listing_rows = self.memory_service.query_episodes(
            room_id=room_id,
            limit=limit,
            offset=offset,
            include_corrected=include_corrected,
        )
        envelopes: list[ObjectEnvelopeRecord] = []
        for row in listing_rows:
            detail_payload = self.memory_service.get_episode_detail(
                room_id=room_id,
                episode_id=str(row["id"]),
            )
            if detail_payload is None:
                continue
            envelopes.append(
                self._build_object_envelope(
                    object_id=f"memory_episode:{row['id']}",
                    object_kind="memory_episode",
                    room_id=str(row["room_id"]),
                    classification_level=str(row["classification_level"]),
                    summary=str(row["title"]),
                    backing_routes=["/api/memory/episodes", "/api/memory/episodes/{episode_id}"],
                    record=dict(detail_payload),
                )
            )
        return envelopes

    def get_object_envelope(
        self,
        *,
        room_id: str,
        object_id: str,
    ) -> ObjectEnvelopeRecord | None:
        object_kind, separator, local_id = object_id.partition(":")
        if not separator or not local_id:
            raise ValueError("object_id must use the '<kind>:<id>' format.")

        if object_kind == "dataset":
            if not local_id.isdigit():
                raise ValueError("dataset object ids must end with a numeric id.")
            row = self.repository.get_dataset(int(local_id), room_id=room_id)
            if row is None:
                return None
            return self._build_object_envelope(
                object_id=object_id,
                object_kind="dataset",
                room_id=str(row["room_id"]),
                classification_level=str(row["classification_level"]),
                summary=str(row["label"]),
                backing_routes=["/api/datasets"],
                record=dict(row),
            )

        if object_kind == "asset":
            if not local_id.isdigit():
                raise ValueError("asset object ids must end with a numeric id.")
            row = self.repository.get_asset(int(local_id), room_id=room_id)
            if row is None:
                return None
            return self._build_object_envelope(
                object_id=object_id,
                object_kind="asset",
                room_id=str(row["room_id"]),
                classification_level=str(row["classification_level"]),
                summary=str(row["relative_path"]),
                backing_routes=["/api/assets", "/api/assets/{asset_id}"],
                record=_decode_service_metadata_row(dict(row)),
            )

        if object_kind == "memory_event":
            if not local_id.isdigit():
                raise ValueError("memory_event object ids must end with a numeric id.")
            payload = self.memory_service.get_event_detail(room_id=room_id, event_id=int(local_id))
            if payload is None:
                return None
            return self._build_object_envelope(
                object_id=object_id,
                object_kind="memory_event",
                room_id=str(payload["room_id"]),
                classification_level=str(payload["classification_level"]),
                summary=str(payload["title"]),
                backing_routes=["/api/memory/events", "/api/memory/events/{event_id}"],
                record=dict(payload),
            )

        if object_kind == "memory_episode":
            payload = self.memory_service.get_episode_detail(room_id=room_id, episode_id=local_id)
            if payload is None:
                return None
            return self._build_object_envelope(
                object_id=object_id,
                object_kind="memory_episode",
                room_id=str(payload["room_id"]),
                classification_level=str(payload["classification_level"]),
                summary=str(payload["title"]),
                backing_routes=["/api/memory/episodes", "/api/memory/episodes/{episode_id}"],
                record=dict(payload),
            )

        raise ValueError(
            "Unsupported object kind. Supported kinds are dataset, asset, memory_event, and memory_episode."
        )

    def query_object_envelopes(
        self,
        *,
        room_id: str,
        object_kind: str,
        limit: int = 20,
        cursor: str | None = None,
    ) -> tuple[list[ObjectEnvelopeRecord], str | None]:
        if object_kind not in self.SUPPORTED_OBJECT_KINDS:
            raise ValueError(
                "Unsupported object kind. Supported kinds are dataset, asset, memory_event, and memory_episode."
            )
        offset = self._parse_cursor(cursor)
        page_limit = limit + 1
        if object_kind == "dataset":
            all_rows = self.list_dataset_envelopes(room_id=room_id)
            return self._slice_page(all_rows, offset=offset, limit=limit)
        if object_kind == "asset":
            all_rows = self.list_asset_envelopes(room_id=room_id, limit=offset + page_limit)
            return self._slice_page(all_rows, offset=offset, limit=limit)
        if object_kind == "memory_event":
            rows = self.list_memory_event_envelopes(
                room_id=room_id,
                limit=page_limit,
                offset=offset,
            )
            return self._page_from_window(rows, offset=offset, limit=limit)
        rows = self.list_memory_episode_envelopes(
            room_id=room_id,
            limit=page_limit,
            offset=offset,
        )
        return self._page_from_window(rows, offset=offset, limit=limit)

    def _build_object_envelope(
        self,
        *,
        object_id: str,
        object_kind: str,
        room_id: str,
        classification_level: str,
        summary: str | None,
        backing_routes: list[str],
        record: dict[str, object],
    ) -> ObjectEnvelopeRecord:
        return ObjectEnvelopeRecord(
            object_id=object_id,
            object_kind=object_kind,
            room_id=room_id,
            classification_level=classification_level,
            version=self.VERSION,
            summary=summary,
            read_only=True,
            backing_routes=backing_routes,
            record=record,
        )

    @staticmethod
    def _parse_cursor(cursor: str | None) -> int:
        if cursor is None:
            return 0
        if not cursor.isdigit():
            raise ValueError("cursor must be a non-negative integer string.")
        return int(cursor)

    @staticmethod
    def _slice_page(
        rows: list[ObjectEnvelopeRecord],
        *,
        offset: int,
        limit: int,
    ) -> tuple[list[ObjectEnvelopeRecord], str | None]:
        window = rows[offset : offset + limit + 1]
        return _ObjectEnvelopeProjector._page_from_window(window, offset=offset, limit=limit)

    @staticmethod
    def _page_from_window(
        window: list[ObjectEnvelopeRecord],
        *,
        offset: int,
        limit: int,
    ) -> tuple[list[ObjectEnvelopeRecord], str | None]:
        if len(window) > limit:
            return window[:limit], str(offset + limit)
        return window, None


@dataclass(frozen=True)
class ServiceContainer:
    memory: MemoryFacade
    policy: PolicyService
    simulation: SimulationService
    audit: AuditService
    blob: BlobService
    art: ArtLabService
    constitution: ConstitutionService
    dialogue_corpus: DialogueCorpusService
    object_envelope: _ObjectEnvelopeProjector

    @classmethod
    def build(cls, repository: KloneRepository) -> "ServiceContainer":
        return cls(
            memory=MemoryFacade(repository),
            policy=PolicyService(),
            simulation=SimulationService(repository),
            audit=AuditService(repository),
            blob=BlobService(repository),
            art=ArtLabService(repository),
            constitution=ConstitutionService(),
            dialogue_corpus=DialogueCorpusService(),
            object_envelope=_ObjectEnvelopeProjector(repository),
        )

    def seam_descriptors(self) -> list[ServiceSeamRecord]:
        return [
            self.memory.seam_descriptor(),
            self.policy.seam_descriptor(),
            self.simulation.seam_descriptor(),
            ServiceSeamRecord(
                id="audit-service",
                name="AuditService",
                implementation="in_process",
                status="active",
                notes=[
                    "Reuses the append-only deterministic audit pipeline already in the monolith.",
                    "No new write authority is exposed through /v1.",
                ],
            ),
            self.blob.seam_descriptor(),
            self.art.seam_descriptor(),
            self.constitution.seam_descriptor(),
            self.dialogue_corpus.seam_descriptor(),
            self.object_envelope.seam_descriptor(),
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
            *self.simulation.public_capabilities(),
            *self.memory.public_capabilities(),
            *self.blob.public_capabilities(),
            *self.art.public_capabilities(),
            *self.constitution.public_capabilities(),
            *self.dialogue_corpus.public_capabilities(),
            *self.object_envelope.public_capabilities(),
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
            PublicCapabilityRecord(
                id="v1.changes.read",
                name="V1 Room Change Preview",
                category="changes",
                path="/v1/rooms/{room_id}/changes",
                methods=["GET"],
                read_only=True,
                room_scoped=True,
                status="available",
                description="Read deterministic room-scoped change preview rows through the versioned public control-plane seam.",
                backed_by=["AuditService", "PolicyService"],
            ),
        ]
