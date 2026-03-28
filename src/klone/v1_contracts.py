from __future__ import annotations

from .schemas import ContractFieldRecord, PublicContractRecord


def contract_registry_payload() -> list[PublicContractRecord]:
    return [
        PublicContractRecord(
            id="object-shell",
            name="Object Shell",
            category="object",
            status="contract_shell",
            route_readiness="public_read_only_get_available",
            description="Stable read-model shell for governed objects exposed through future /v1 object surfaces.",
            notes=[
                "Defines the canonical object envelope before any public object mutation routes exist.",
                "Must remain compatible with room scoping and evidence immutability rules.",
                "Current local envelope visibility is projected through existing governed read routes only.",
                "POST /v1/rooms/{room_id}/objects/get is the first public read-only object route.",
            ],
            backing_routes=[
                "/v1/rooms/{room_id}/objects/get",
                "/api/datasets",
                "/api/assets",
                "/api/memory/events",
                "/api/memory/episodes",
            ],
            fields=[
                ContractFieldRecord(
                    name="object_id",
                    field_type="string",
                    required=True,
                    description="Stable public identifier for the object.",
                ),
                ContractFieldRecord(
                    name="object_kind",
                    field_type="string",
                    required=True,
                    description="Canonical object category such as dataset, asset, memory_event, or memory_episode.",
                ),
                ContractFieldRecord(
                    name="room_id",
                    field_type="string",
                    required=True,
                    description="Owning room scope for the object.",
                ),
                ContractFieldRecord(
                    name="classification_level",
                    field_type="string",
                    required=True,
                    description="Governance classification carried with the object.",
                ),
                ContractFieldRecord(
                    name="version",
                    field_type="integer",
                    required=True,
                    description="Monotonic object version or compatibility marker.",
                ),
                ContractFieldRecord(
                    name="summary",
                    field_type="string",
                    required=False,
                    description="Bounded human-readable summary safe for the current surface.",
                ),
                ContractFieldRecord(
                    name="read_only",
                    field_type="boolean",
                    required=True,
                    description="Indicates that the public object envelope is read-only.",
                ),
                ContractFieldRecord(
                    name="backing_routes",
                    field_type="array[string]",
                    required=True,
                    description="Existing governed routes that back the object envelope projection.",
                ),
                ContractFieldRecord(
                    name="record",
                    field_type="object",
                    required=True,
                    description="Structured room-scoped object payload derived from the underlying governed read model.",
                ),
            ],
        ),
        PublicContractRecord(
            id="query-shell",
            name="Query Shell",
            category="query",
            status="contract_shell",
            route_readiness="public_read_only_query_available",
            description="Stable read-only query envelope for deterministic public room-scoped list flows without committing to search semantics.",
            notes=[
                "Does not imply semantic search, embeddings, or fuzzy matching.",
                "The shell exists to keep query inputs deterministic and auditable.",
                "POST /v1/rooms/{room_id}/query is the first public read-only query route.",
            ],
            backing_routes=[
                "/v1/rooms/{room_id}/query",
                "/api/memory/events",
                "/api/memory/episodes",
            ],
            fields=[
                ContractFieldRecord(
                    name="query_id",
                    field_type="string",
                    required=True,
                    description="Stable identifier for the query execution.",
                ),
                ContractFieldRecord(
                    name="query_kind",
                    field_type="string",
                    required=True,
                    description="Type of query such as list, detail, context, or audit preview.",
                ),
                ContractFieldRecord(
                    name="room_id",
                    field_type="string",
                    required=False,
                    description="Optional explicit room boundary for room-scoped queries.",
                ),
                ContractFieldRecord(
                    name="filters",
                    field_type="object",
                    required=False,
                    description="Deterministic filter mapping for the query.",
                ),
                ContractFieldRecord(
                    name="cursor",
                    field_type="string",
                    required=False,
                    description="Reserved continuation token field; the current public query route uses deterministic limit/offset pagination.",
                ),
                ContractFieldRecord(
                    name="limit",
                    field_type="integer",
                    required=False,
                    description="Bounded result size for the current room-scoped query.",
                ),
                ContractFieldRecord(
                    name="request_id",
                    field_type="string",
                    required=True,
                    description="Inbound request identifier propagated through the query lifecycle.",
                ),
            ],
        ),
        PublicContractRecord(
            id="change-shell",
            name="Change Shell",
            category="changes",
            status="contract_shell",
            route_readiness="no_public_route_yet",
            description="Append-only change envelope intended to align future public change surfaces with audit reuse.",
            notes=[
                "This shell is append-only by design and should reuse audit lineage rather than overwrite history.",
                "No public /v1 changes route exists yet.",
            ],
            fields=[
                ContractFieldRecord(
                    name="change_id",
                    field_type="string",
                    required=True,
                    description="Stable identifier for the append-only change record.",
                ),
                ContractFieldRecord(
                    name="object_id",
                    field_type="string",
                    required=True,
                    description="Public identifier for the changed object.",
                ),
                ContractFieldRecord(
                    name="change_kind",
                    field_type="string",
                    required=True,
                    description="Declared change type such as created, indexed, corrected, or superseded.",
                ),
                ContractFieldRecord(
                    name="trace_id",
                    field_type="string",
                    required=True,
                    description="Trace identifier linking the change to request context and audit.",
                ),
                ContractFieldRecord(
                    name="recorded_at",
                    field_type="datetime",
                    required=True,
                    description="Append-only timestamp for the change record.",
                ),
                ContractFieldRecord(
                    name="actor",
                    field_type="string",
                    required=True,
                    description="Actor or principal placeholder associated with the change.",
                ),
            ],
        ),
        PublicContractRecord(
            id="blob-shell",
            name="Blob Metadata Shell",
            category="blob",
            status="contract_shell",
            route_readiness="metadata_only_no_public_upload",
            description="Local blob metadata shell that reserves the future public blob boundary without exposing upload routes.",
            notes=[
                "POST /v1/rooms/{room_id}/blobs/get is the first public read-only blob metadata route.",
                "No /v1 blobs upload route exists yet.",
                "This shell is metadata-only and remains local-first.",
            ],
            backing_routes=[
                "/v1/rooms/{room_id}/blobs/get",
                "/api/assets",
                "/api/assets/{asset_id}",
            ],
            fields=[
                ContractFieldRecord(
                    name="blob_id",
                    field_type="string",
                    required=True,
                    description="Stable public identifier for the blob metadata record.",
                ),
                ContractFieldRecord(
                    name="media_type",
                    field_type="string",
                    required=True,
                    description="Canonical media type for the blob.",
                ),
                ContractFieldRecord(
                    name="size_bytes",
                    field_type="integer",
                    required=True,
                    description="Recorded blob size in bytes.",
                ),
                ContractFieldRecord(
                    name="sha256",
                    field_type="string",
                    required=True,
                    description="Content hash for deterministic blob identity.",
                ),
                ContractFieldRecord(
                    name="storage_kind",
                    field_type="string",
                    required=True,
                    description="Local storage backend category for the blob metadata record.",
                ),
                ContractFieldRecord(
                    name="linked_object_id",
                    field_type="string",
                    required=False,
                    description="Optional owning object identifier for object-to-blob linkage.",
                ),
            ],
        ),
    ]
