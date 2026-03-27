from typing import Any

from pydantic import BaseModel, Field

from .contracts import (
    AssetKind,
    ClassificationLevel,
    DedupStatus,
    ExtractionStatus,
    GuardDecision,
    IngestStatus,
    MemoryEntityType,
    MemoryEpisodeType,
    MemoryOwnerType,
    MemoryProvenanceType,
    MemoryStatus,
    RoomStatus,
    RoomType,
)


class DatasetIngestRequest(BaseModel):
    label: str = Field(..., min_length=1, max_length=120)
    root_path: str = Field(..., min_length=1)
    collection: str = Field(default="default", min_length=1, max_length=120)
    classification_level: ClassificationLevel = "personal"
    description: str | None = Field(default=None, max_length=500)


class DatasetRecord(BaseModel):
    id: int
    slug: str
    label: str
    root_path: str
    room_id: str
    collection: str
    description: str | None = None
    classification_level: ClassificationLevel
    scan_state: IngestStatus | None = None
    last_scan_at: str | None = None
    asset_count: int = 0
    duplicate_count: int = 0
    created_at: str
    updated_at: str


class AssetRecord(BaseModel):
    id: int
    dataset_id: int
    dataset_label: str
    room_id: str
    path: str
    relative_path: str
    file_name: str
    extension: str
    mime_type: str | None = None
    size_bytes: int
    sha256: str
    asset_kind: AssetKind
    classification_level: ClassificationLevel
    extraction_status: ExtractionStatus
    dedup_status: DedupStatus
    canonical_asset_id: int | None = None
    fs_created_at: str
    fs_modified_at: str
    indexed_at: str
    first_seen_at: str
    last_seen_at: str
    collection: str
    metadata: dict[str, Any] | None = None


class IngestRunRecord(BaseModel):
    id: int
    dataset_id: int
    dataset_label: str
    room_id: str
    status: IngestStatus
    trigger_source: str
    started_at: str
    completed_at: str | None = None
    files_discovered: int
    assets_indexed: int
    new_assets: int
    updated_assets: int
    unchanged_assets: int
    duplicates_detected: int
    errors_detected: int
    summary: str | None = None


class AuditEventRecord(BaseModel):
    id: int
    event_type: str
    actor: str
    target_type: str
    target_id: str | None = None
    room_id: str | None = None
    classification_level: ClassificationLevel
    summary: str
    metadata: dict[str, Any] | None = None
    created_at: str


class RoomRecord(BaseModel):
    id: str
    label: str
    room_type: RoomType
    classification: ClassificationLevel
    supervisor: str
    status: RoomStatus
    allowed_agents: list[str]
    allowed_roles: list[str]
    retention_policy: str
    permissions: list[str]
    audit_visibility: str
    approval_rules: list[str]


class PermissionLevelRecord(BaseModel):
    id: str
    description: str


class GuardResultRecord(BaseModel):
    guard_name: str
    decision: GuardDecision
    reason: str
    requires_supervisor: bool


class GovernanceGuardRecord(BaseModel):
    name: str
    description: str
    active: bool
    latest_result: GuardResultRecord | None = None


class MissionControlStatus(BaseModel):
    app_name: str
    environment: str
    owner_debug_mode: bool
    database_path: str
    dataset_count: int
    indexed_asset_count: int
    duplicate_asset_count: int
    audit_event_count: int
    latest_ingest: IngestRunRecord | None = None
    room_count: int
    module_count: int
    agent_count: int
    guard_count: int


class IngestStatusResponse(BaseModel):
    queue_depth: int
    latest_run: IngestRunRecord | None = None
    recent_runs: list[IngestRunRecord]


class IngestExecutionResponse(BaseModel):
    dataset: DatasetRecord
    run: IngestRunRecord
    errors: list[str]


class MemoryEventRecord(BaseModel):
    id: int
    room_id: str
    classification_level: ClassificationLevel
    event_type: str
    source_table: str
    source_record_id: str
    dataset_id: int | None = None
    asset_id: int | None = None
    ingest_run_id: int | None = None
    occurred_at: str
    recorded_at: str
    title: str
    evidence_text: str
    status: MemoryStatus = "active"
    correction_reason: str | None = None
    superseded_by_id: int | None = None
    corrected_at: str | None = None
    corrected_by_role: str | None = None
    metadata: dict[str, Any] | None = None
    created_at: str
    updated_at: str


class MemoryEntityRecord(BaseModel):
    id: int
    room_id: str
    classification_level: ClassificationLevel
    entity_type: MemoryEntityType
    canonical_name: str
    canonical_key: str
    seed_source_event_id: int
    first_seen_at: str
    last_seen_at: str
    metadata: dict[str, Any] | None = None
    created_at: str
    updated_at: str


class MemoryEpisodeRecord(BaseModel):
    id: str
    room_id: str
    classification_level: ClassificationLevel
    episode_type: MemoryEpisodeType
    grouping_basis: str
    source_table: str
    source_record_id: str
    title: str
    summary: str
    status: MemoryStatus = "active"
    correction_reason: str | None = None
    corrected_at: str | None = None
    corrected_by_role: str | None = None
    start_at: str
    end_at: str
    metadata: dict[str, Any] | None = None
    created_at: str
    updated_at: str


class MemoryEventEntityLinkRecord(BaseModel):
    event_id: int
    entity_id: int
    role: str
    source_basis: str
    created_at: str


class MemoryEpisodeEventLinkRecord(BaseModel):
    episode_id: str
    event_id: int
    sequence_no: int
    inclusion_basis: str
    created_at: str


class MemoryProvenanceRecord(BaseModel):
    id: int
    room_id: str
    owner_type: MemoryOwnerType
    owner_id: str
    provenance_type: MemoryProvenanceType
    source_table: str
    source_record_id: str
    source_field: str | None = None
    basis_type: str
    basis_value: str | None = None
    created_at: str


class MemoryLinkedEntityRecord(BaseModel):
    entity_id: int
    room_id: str
    classification_level: ClassificationLevel
    entity_type: MemoryEntityType
    canonical_name: str
    canonical_key: str
    first_seen_at: str
    last_seen_at: str
    role: str
    source_basis: str
    metadata: dict[str, Any] | None = None


class MemoryEpisodeMemberRecord(BaseModel):
    sequence_no: int
    inclusion_basis: str
    event: MemoryEventRecord


class MemorySeedResult(BaseModel):
    room_id: str | None = None
    ingest_run_id: int | None = None
    seed_version: str
    events_written: int = 0
    events_upserted: int = 0
    events_skipped: int = 0
    entities_written: int = 0
    entities_upserted: int = 0
    entities_skipped: int = 0
    episodes_written: int = 0
    episodes_upserted: int = 0
    episodes_skipped: int = 0
    event_entity_links_written: int = 0
    event_entity_links_upserted: int = 0
    event_entity_links_skipped: int = 0
    episode_event_links_written: int = 0
    episode_event_links_upserted: int = 0
    episode_event_links_skipped: int = 0
    provenance_written: int = 0
    provenance_upserted: int = 0
    provenance_skipped: int = 0


class MemoryReplayRequestInternal(BaseModel):
    room_id: str
    ingest_run_id: int | None = None
    actor_role: str = "owner"
    seed_version: str


class MemoryReplayResult(MemorySeedResult):
    pass


class MemoryCorrectionResult(BaseModel):
    room_id: str
    memory_kind: str
    memory_id: str
    operation: str
    previous_status: MemoryStatus
    resulting_status: MemoryStatus
    superseded_by_id: int | None = None
    corrected_at: str
    corrected_by_role: str


class MemoryEventDetailRecord(MemoryEventRecord):
    corrected: bool
    source_lineage: list[MemoryProvenanceRecord]
    seed_basis: list[MemoryProvenanceRecord]
    provenance: list[MemoryProvenanceRecord]
    linked_entities: list[MemoryLinkedEntityRecord]


class MemoryEpisodeDetailRecord(MemoryEpisodeRecord):
    source_lineage: list[MemoryProvenanceRecord]
    seed_basis: list[MemoryProvenanceRecord]
    membership_basis: list[MemoryProvenanceRecord]
    provenance: list[MemoryProvenanceRecord]
    linked_events: list[MemoryEpisodeMemberRecord]
