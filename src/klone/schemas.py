from typing import Any, Literal

from pydantic import BaseModel, Field

from .contracts import (
    AssetKind,
    ClassificationLevel,
    DedupStatus,
    ExtractionStatus,
    GuardDecision,
    IngestQueueStatus,
    IngestStatus,
    InternalRunKind,
    InternalRunStatus,
    InternalRunTrigger,
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


class ArtAssetMetricsRecord(BaseModel):
    analysis_version: str
    asset_id: int
    room_id: str
    classification_level: ClassificationLevel
    asset_kind: AssetKind
    file_name: str
    relative_path: str
    width_px: int
    height_px: int
    sample_width_px: int
    sample_height_px: int
    orientation: Literal["portrait", "landscape", "square"]
    aspect_ratio: float
    brightness_mean: float
    contrast_stddev: float
    dark_pixel_ratio: float
    light_pixel_ratio: float
    ink_coverage_ratio: float
    edge_density: float
    colorfulness: float
    entropy: float
    symmetry_vertical: float
    symmetry_horizontal: float
    center_of_mass_x: float
    center_of_mass_y: float
    quantized_color_count: int
    notes: list[str]
    warnings: list[str]


class ArtAssetComparisonItemRecord(BaseModel):
    position: int
    asset_id: int
    dataset_label: str
    room_id: str
    asset_kind: AssetKind
    file_name: str
    relative_path: str
    fs_modified_at: str
    indexed_at: str
    metrics: ArtAssetMetricsRecord


class ArtAssetMetricDeltaRecord(BaseModel):
    metric_name: str
    start_asset_id: int
    end_asset_id: int
    start_value: float
    end_value: float
    delta: float


class ArtAssetComparisonRecord(BaseModel):
    comparison_version: str
    analysis_version: str
    room_id: str
    read_only: bool = True
    requested_asset_ids: list[int]
    ordered_asset_ids: list[int]
    asset_count: int
    ordering_basis: Literal["fs_modified_at"]
    compared_assets: list[ArtAssetComparisonItemRecord]
    metric_deltas: list[ArtAssetMetricDeltaRecord]
    notes: list[str]
    warnings: list[str]


class ConstitutionParameterRecord(BaseModel):
    key: str
    value: float
    min_value: float
    max_value: float
    category: str
    description: str


class ConstitutionChangeRecord(BaseModel):
    version: str
    changed_at: str
    actor: str
    summary: str
    effect_scope: str
    notes: list[str]


class ConstitutionSnapshotRecord(BaseModel):
    profile_id: str
    layer_version: str
    summary: str
    approval_state: str
    read_only: bool = True
    routing_influence_enabled: bool = False
    parameter_count: int
    change_count: int
    parameters: list[ConstitutionParameterRecord]
    recent_changes: list[ConstitutionChangeRecord]
    notes: list[str]
    warnings: list[str]


class DialogueCorpusAnalysisRequest(BaseModel):
    source_path: str = Field(..., min_length=1)
    owner_name: str | None = Field(default=None, min_length=1, max_length=200)


class DialogueCorpusAnswerRequest(BaseModel):
    source_path: str = Field(..., min_length=1)
    question: str = Field(..., min_length=1, max_length=320)
    owner_name: str | None = Field(default=None, min_length=1, max_length=200)


class CloneChatMessageRecord(BaseModel):
    role: Literal["system", "user", "assistant"]
    speaker: str
    content: str


class CloneChatRequest(BaseModel):
    source_path: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1, max_length=4000)
    owner_name: str | None = Field(default=None, min_length=1, max_length=200)
    mode: Literal["auto", "bounded", "gpt-5.4"] = "auto"
    history: list[CloneChatMessageRecord] = Field(default_factory=list, max_length=24)


class CloneChatOpenAIConfigRequest(BaseModel):
    api_key: str = Field(..., min_length=20, max_length=400)
    persist: bool = True


class CloneChatOpenAIConfigResponse(BaseModel):
    configured: bool
    persisted: bool
    key_source: str
    preferred_model: str
    note: str


class DialogueCorpusSourceRecord(BaseModel):
    label: str
    path: str
    record_count: int
    status: str
    selected: bool


class DialogueCorpusSectionRecord(BaseModel):
    section: str
    thread_count: int
    message_count: int


class DialogueCorpusActivityBucketRecord(BaseModel):
    bucket: str
    thread_count: int
    message_count: int
    sent_message_count: int
    received_message_count: int


class DialogueCorpusCounterpartRecord(BaseModel):
    name: str
    thread_count: int
    sent_message_count: int
    received_message_count: int
    interaction_message_count: int
    first_message_at: str | None = None
    last_message_at: str | None = None
    sections: list[str]


class DialogueCorpusGroupThreadRecord(BaseModel):
    title: str
    participant_count: int
    message_count: int
    first_message_at: str | None = None
    last_message_at: str | None = None
    sections: list[str]


class DialogueCorpusTopicRecord(BaseModel):
    token: str
    count: int


class DialogueCorpusStyleSignalRecord(BaseModel):
    key: str
    label: str
    value: float
    unit: str
    summary: str


class DialogueCorpusAnswerSourceRecord(BaseModel):
    content: str
    source_refs: list[str]


class DialogueCorpusAnalysisRecord(BaseModel):
    analysis_version: str
    source_kind: str
    requested_path: str
    selected_source_path: str
    owner_name: str
    recommended_room_id: str
    recommended_classification_level: ClassificationLevel
    read_only: bool = True
    thread_count: int
    direct_thread_count: int
    group_thread_count: int
    counterpart_count: int
    unique_participant_count: int
    message_count: int
    sent_message_count: int
    received_message_count: int
    attachment_message_count: int
    first_message_at: str | None = None
    last_message_at: str | None = None
    detected_sources: list[DialogueCorpusSourceRecord]
    section_breakdown: list[DialogueCorpusSectionRecord]
    activity_by_year: list[DialogueCorpusActivityBucketRecord]
    top_counterparts: list[DialogueCorpusCounterpartRecord]
    top_group_threads: list[DialogueCorpusGroupThreadRecord]
    top_terms: list[DialogueCorpusTopicRecord]
    style_signals: list[DialogueCorpusStyleSignalRecord]
    relationship_priors: list[str]
    history_priors: list[str]
    clone_foundation: list[str]
    notes: list[str]
    warnings: list[str]


class DialogueCorpusAnswerRecord(BaseModel):
    answer_version: str
    analysis_version: str
    source_kind: str
    requested_path: str
    selected_source_path: str
    owner_name: str
    question: str
    query_kind: str
    supported: bool
    read_only: bool = True
    source_backed_content: list[DialogueCorpusAnswerSourceRecord]
    derived_explanation: str | None = None
    uncertainty: list[str]
    limitations: list[str]
    suggested_queries: list[str]


class CloneChatStatusRecord(BaseModel):
    default_source_path: str | None = None
    openai_api_configured: bool
    openai_key_source: str | None = None
    preferred_model: str
    available_modes: list[str]
    channel_name: str
    notes: list[str]
    suggested_queries: list[str]


class CloneChatResponseRecord(BaseModel):
    requested_mode: str
    backend_mode: str
    model: str | None = None
    openai_api_configured: bool
    llm_call_performed: bool = False
    reply: CloneChatMessageRecord
    answer: DialogueCorpusAnswerRecord
    system_notes: list[str]
    suggested_queries: list[str]


class BlobMetadataRecord(BaseModel):
    blob_id: str
    asset_id: int
    linked_object_id: str | None = None
    dataset_id: int
    dataset_label: str
    room_id: str
    classification_level: ClassificationLevel
    asset_kind: AssetKind
    media_type: str
    storage_kind: str
    size_bytes: int
    sha256: str
    dedup_status: DedupStatus
    canonical_blob_id: str | None = None
    file_name: str
    relative_path: str
    indexed_at: str
    metadata: dict[str, Any] | None = None


class ObjectEnvelopeRecord(BaseModel):
    object_id: str
    object_kind: str
    room_id: str
    classification_level: ClassificationLevel
    version: int
    summary: str | None = None
    read_only: bool = True
    backing_routes: list[str]
    record: dict[str, Any]


class IngestRunRecord(BaseModel):
    id: int
    dataset_id: int
    dataset_label: str
    room_id: str
    classification_level: ClassificationLevel | None = None
    collection: str | None = None
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
    has_manifest: bool = False


class IngestQueueJobRecord(BaseModel):
    id: int
    label: str
    normalized_root_path: str
    room_id: str
    classification_level: ClassificationLevel
    collection: str
    description: str | None = None
    status: IngestQueueStatus
    created_at: str
    updated_at: str
    started_at: str | None = None
    completed_at: str | None = None
    attempt_count: int
    last_run_id: int | None = None
    last_error: str | None = None
    can_execute: bool
    can_cancel: bool


class IngestManifestKindRecord(BaseModel):
    asset_kind: AssetKind
    count: int
    total_size_bytes: int


class IngestManifestSampleRecord(BaseModel):
    relative_path: str
    file_name: str
    asset_kind: AssetKind
    mime_type: str | None = None
    size_bytes: int
    planned_action: Literal["new", "updated", "unchanged"]
    dedup_status: DedupStatus
    canonical_asset_id: int | None = None
    canonical_dataset_label: str | None = None
    canonical_relative_path: str | None = None


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


class ControlPlaneAuditRecord(BaseModel):
    id: int
    event_type: str
    route_path: str
    actor: str
    actor_role: str
    principal: str
    request_id: str
    trace_id: str
    status_code: int
    summary: str
    metadata: dict[str, Any] | None = None
    prev_event_hash: str | None = None
    event_hash: str
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


class RuntimeConfigRecord(BaseModel):
    app_name: str
    app_version: str
    environment: str
    owner_debug_mode: bool
    project_root: str
    data_dir: str
    database_path: str
    asset_preview_limit: int
    audit_preview_limit: int
    bootstrap_version: str
    schema_version: str
    module_registry_version: str


class BootstrapStatusRecord(BaseModel):
    bootstrap_version: str
    schema_version: str
    schema_user_version: int
    bootstrap_mode: str
    database_path: str
    initialized_at: str
    expected_tables: list[str]
    actual_tables: list[str]
    missing_tables: list[str]
    correction_schema_ready: bool


class ModuleCapabilityRecord(BaseModel):
    id: str
    name: str
    stage: str
    status: str
    supervisor: str
    key_inputs: list[str]
    outputs: list[str]
    capability_count: int


class InternalRunRecord(BaseModel):
    id: str
    task_id: str
    run_kind: InternalRunKind
    status: InternalRunStatus
    trigger: InternalRunTrigger
    room_id: str | None = None
    trace_id: str
    started_at: str
    completed_at: str | None = None
    metadata: dict[str, Any] | None = None


class RequestContextRecord(BaseModel):
    request_id: str
    trace_id: str
    principal: str
    actor_role: str


class PublicBlobGetResponse(BaseModel):
    api_version: str
    request_context: RequestContextRecord
    room_id: str
    blob: BlobMetadataRecord


class PublicObjectGetRequest(BaseModel):
    object_id: str = Field(..., min_length=1)


class PublicObjectGetResponse(BaseModel):
    api_version: str
    request_context: RequestContextRecord
    room_id: str
    object: ObjectEnvelopeRecord


class PublicQueryRequest(BaseModel):
    query_kind: Literal["memory_events", "memory_episodes", "audit_preview"]
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    status: MemoryStatus | None = None
    event_type: str | None = Field(default=None, min_length=1)
    episode_type: MemoryEpisodeType | None = None
    target_type: str | None = Field(default=None, min_length=1)
    ingest_run_id: int | None = Field(default=None, ge=1)
    include_corrected: bool = True


class PublicQueryResponse(BaseModel):
    api_version: str
    request_context: RequestContextRecord
    room_id: str
    query_id: str
    query_kind: Literal["memory_events", "memory_episodes", "audit_preview"]
    read_only: bool = True
    limit: int
    offset: int
    result_count: int
    filters: dict[str, Any]
    backing_routes: list[str]
    results: list[dict[str, Any]]


class PublicChangePreviewRecord(BaseModel):
    change_id: str
    object_id: str
    change_kind: str
    trace_id: str
    recorded_at: str
    actor: str
    summary: str


class PublicChangePreviewResponse(BaseModel):
    api_version: str
    request_context: RequestContextRecord
    room_id: str
    read_only: bool = True
    limit: int
    offset: int
    result_count: int
    filters: dict[str, Any]
    backing_routes: list[str]
    changes: list[PublicChangePreviewRecord]


class ServiceSeamRecord(BaseModel):
    id: str
    name: str
    implementation: str
    status: str
    notes: list[str]


class PublicCapabilityRecord(BaseModel):
    id: str
    name: str
    category: str
    path: str
    methods: list[str]
    read_only: bool
    room_scoped: bool
    status: str
    description: str
    backed_by: list[str]


class ContractFieldRecord(BaseModel):
    name: str
    field_type: str
    required: bool
    description: str


class PublicContractRecord(BaseModel):
    id: str
    name: str
    category: str
    status: str
    description: str
    route_readiness: str
    notes: list[str]
    backing_routes: list[str] = Field(default_factory=list)
    fields: list[ContractFieldRecord]


class PublicCapabilitiesResponse(BaseModel):
    api_version: str
    request_context: RequestContextRecord
    services: list[ServiceSeamRecord]
    module_registry: list[ModuleCapabilityRecord]
    capabilities: list[PublicCapabilityRecord]
    contracts: list[PublicContractRecord]


class MissionControlStatus(BaseModel):
    app_name: str
    app_version: str
    environment: str
    owner_debug_mode: bool
    database_path: str
    schema_version: str
    bootstrap_version: str
    module_registry_version: str
    dataset_count: int
    indexed_asset_count: int
    duplicate_asset_count: int
    audit_event_count: int
    latest_ingest: IngestRunRecord | None = None
    room_count: int
    module_count: int
    agent_count: int
    guard_count: int
    runtime_config: RuntimeConfigRecord
    bootstrap: BootstrapStatusRecord
    module_registry: list[ModuleCapabilityRecord]
    latest_internal_run: InternalRunRecord | None = None
    recent_internal_runs: list[InternalRunRecord]


class HybridBoardAxisRecord(BaseModel):
    id: str
    index: int
    label: str
    description: str


class HybridBoardSourceTotalsRecord(BaseModel):
    memory_events: int
    memory_episodes: int
    audit_events: int


class HybridBoardSourceRecord(BaseModel):
    source_kind: Literal["audit", "memory_event", "memory_episode"]
    source_id: str
    room_id: str
    title: str
    summary: str
    status: str | None = None
    occurred_at: str | None = None
    route_hint: str | None = None
    markers: list[str]


class HybridBoardWorldMemoryClusterRefRecord(BaseModel):
    cluster_id: str
    room_id: str
    dataset_label: str
    label: str
    node_count: int
    dominant_asset_kind: str
    primary_square_id: str | None = None
    primary_square_title: str | None = None
    place_score: float


class HybridBoardWorldMemoryNodeRefRecord(BaseModel):
    node_id: str
    cluster_id: str
    room_id: str
    label: str
    anchor_type: str
    asset_kind: str
    primary_square_id: str
    primary_square_title: str
    place_score: float
    depth_candidate: bool


class HybridBoardSquareRecord(BaseModel):
    square_id: str
    row_id: str
    row_index: int
    column_id: str
    column_index: int
    title: str
    dominant_polarity: Literal["infernal", "celestial", "neutral"]
    infernal_pressure: float
    celestial_pressure: float
    neutral_residue: float
    scar_score: float
    activity_score: float
    intensity: float
    alignment_score: float
    signal_count: int
    event_count: int
    episode_count: int
    audit_count: int
    source_room_ids: list[str]
    top_markers: list[str]
    last_touched_at: str | None = None


class HybridMemoryBoardRecord(BaseModel):
    projection_version: str
    read_only: bool = True
    requested_room_id: str | None = None
    resolved_room_ids: list[str]
    square_count: int
    source_totals: HybridBoardSourceTotalsRecord
    row_axes: list[HybridBoardAxisRecord]
    column_axes: list[HybridBoardAxisRecord]
    squares: list[HybridBoardSquareRecord]
    notes: list[str]
    warnings: list[str]


class HybridBoardSquareDetailRecord(BaseModel):
    projection_version: str
    read_only: bool = True
    requested_room_id: str | None = None
    resolved_room_ids: list[str]
    row_axes: list[HybridBoardAxisRecord]
    column_axes: list[HybridBoardAxisRecord]
    square: HybridBoardSquareRecord
    source_count: int
    sources: list[HybridBoardSourceRecord]
    linked_cluster_count: int = 0
    linked_node_count: int = 0
    linked_clusters: list[HybridBoardWorldMemoryClusterRefRecord] = Field(default_factory=list)
    linked_nodes: list[HybridBoardWorldMemoryNodeRefRecord] = Field(default_factory=list)
    notes: list[str]
    warnings: list[str]


class WorldMemorySquareLinkRecord(BaseModel):
    square_id: str
    row_id: str
    column_id: str
    title: str
    weight: float


class WorldMemoryPlaceShellRecord(BaseModel):
    stage: str
    eligible: bool
    depth_candidate: bool
    place_score: float
    rationale: str
    cues: list[str]


class WorldMemoryClusterRecord(BaseModel):
    cluster_id: str
    room_id: str
    dataset_id: int
    dataset_label: str
    anchor_prefix: str
    label: str
    node_count: int
    dominant_asset_kind: str
    primary_square_id: str | None = None
    primary_square_title: str | None = None
    place_score: float = 0.0
    image_candidate_count: int = 0
    depth_candidate_count: int = 0
    recent_indexed_at: str | None = None


class WorldMemoryNodeRecord(BaseModel):
    node_id: str
    cluster_id: str
    room_id: str
    dataset_id: int
    dataset_label: str
    asset_id: int
    asset_kind: str
    anchor_type: str
    label: str
    relative_path: str
    file_name: str
    size_bytes: int
    intensity: float
    primary_square_id: str
    primary_square_title: str
    place_score: float
    depth_candidate: bool
    indexed_at: str
    fs_modified_at: str


class WorldMemoryRecord(BaseModel):
    projection_version: str
    read_only: bool = True
    requested_room_id: str | None = None
    resolved_room_ids: list[str]
    node_count: int
    cluster_count: int
    place_candidate_count: int
    depth_candidate_count: int
    anchor_types: list[str]
    clusters: list[WorldMemoryClusterRecord]
    nodes: list[WorldMemoryNodeRecord]
    notes: list[str]
    warnings: list[str]


class WorldMemoryClusterDetailRecord(BaseModel):
    projection_version: str
    read_only: bool = True
    requested_room_id: str | None = None
    resolved_room_ids: list[str]
    cluster: WorldMemoryClusterRecord
    linked_squares: list[WorldMemorySquareLinkRecord]
    nodes: list[WorldMemoryNodeRecord]
    notes: list[str]
    warnings: list[str]


class WorldMemoryNodeDetailRecord(BaseModel):
    projection_version: str
    read_only: bool = True
    requested_room_id: str | None = None
    resolved_room_ids: list[str]
    node: WorldMemoryNodeRecord
    linked_square: WorldMemorySquareLinkRecord
    place_shell: WorldMemoryPlaceShellRecord
    metadata: dict[str, Any] | None = None
    notes: list[str]
    warnings: list[str]


class WorldMemoryDepthJobRequest(BaseModel):
    node_ids: list[str] = Field(..., min_length=1, max_length=6)
    renderer: Literal["local_luma_shell", "depth_anything_v2_remote"] = "local_luma_shell"


class WorldMemoryDepthJobNodeRecord(BaseModel):
    node_id: str
    cluster_id: str
    asset_id: int
    label: str
    relative_path: str
    asset_kind: AssetKind
    renderer: str
    status: str
    source_image_route: str
    depth_preview_route: str
    depth_raw_route: str
    width_px: int
    height_px: int
    generated_at: str
    notes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class WorldMemoryDepthJobRecord(BaseModel):
    job_id: int
    room_id: str
    renderer: str
    status: str
    node_count: int
    result_count: int
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    requested_node_ids: list[str]
    results: list[WorldMemoryDepthJobNodeRecord] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error_text: str | None = None


class WorldMemoryDepthJobListRecord(BaseModel):
    projection_version: str
    read_only: bool = True
    requested_room_id: str | None = None
    resolved_room_ids: list[str]
    job_count: int
    jobs: list[WorldMemoryDepthJobRecord]
    notes: list[str]
    warnings: list[str]


class WorldMemoryPlaceViewRecord(BaseModel):
    projection_version: str
    read_only: bool = True
    requested_room_id: str | None = None
    resolved_room_ids: list[str]
    node_id: str
    cluster_id: str
    room_id: str
    asset_id: int
    label: str
    relative_path: str
    viewer_kind: Literal["parallax_2_5d"] = "parallax_2_5d"
    source_image_route: str
    depth_preview_route: str | None = None
    depth_raw_route: str | None = None
    latest_job_id: int | None = None
    renderer: str | None = None
    available: bool = False
    notes: list[str]
    warnings: list[str]


class IngestStatusResponse(BaseModel):
    queue_depth: int
    latest_run: IngestRunRecord | None = None
    recent_runs: list[IngestRunRecord]
    latest_queue_job: IngestQueueJobRecord | None = None
    recent_queue_jobs: list[IngestQueueJobRecord] = Field(default_factory=list)


class IngestExecutionResponse(BaseModel):
    dataset: DatasetRecord
    run: IngestRunRecord
    errors: list[str]


class IngestQueueEnqueueResponse(BaseModel):
    job: IngestQueueJobRecord
    created: bool


class IngestQueueExecutionResponse(BaseModel):
    job: IngestQueueJobRecord
    execution: IngestExecutionResponse | None = None
    error: str | None = None


class IngestPreflightResponse(BaseModel):
    request: DatasetIngestRequest
    normalized_root_path: str
    room_id: str
    room_label: str
    existing_dataset_id: int | None = None
    existing_dataset_slug: str | None = None
    classification_guard: GuardResultRecord
    access_guard: GuardResultRecord
    can_start_ingest: bool
    files_discovered: int
    total_size_bytes: int
    planned_new_assets: int
    planned_updated_assets: int
    planned_unchanged_assets: int
    duplicates_detected: int
    asset_kind_breakdown: list[IngestManifestKindRecord]
    sample_limit: int
    sample_assets: list[IngestManifestSampleRecord]
    warnings: list[str]


class IngestRunManifestResponse(BaseModel):
    run: IngestRunRecord
    normalized_root_path: str
    total_size_bytes: int
    asset_kind_breakdown: list[IngestManifestKindRecord]
    sample_limit: int
    sample_assets: list[IngestManifestSampleRecord]
    warnings: list[str]


class IngestQueueHistoryResponse(BaseModel):
    room_id: str
    read_only: bool = True
    history_limit: int
    history_event_count: int
    job: IngestQueueJobRecord
    history_events: list[AuditEventRecord]
    linked_run: IngestRunRecord | None = None
    linked_manifest_available: bool = False
    linked_manifest_route: str | None = None


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
    provenance_summary: "MemoryProvenanceSummaryRecord | None" = None
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
    provenance_summary: "MemoryProvenanceSummaryRecord | None" = None
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


class MemoryEventEpisodeMembershipRecord(BaseModel):
    sequence_no: int
    inclusion_basis: str
    episode: MemoryEpisodeRecord


class MemoryEventSupersessionRecord(BaseModel):
    id: str
    room_id: str
    old_event_id: str
    new_event_id: str
    reason: str | None = None
    created_at: str
    created_by_role: str
    event_role: str


class MemoryProvenanceSummaryRecord(BaseModel):
    total_count: int
    source_lineage_count: int
    seed_basis_count: int
    membership_basis_count: int
    source_refs: list[str]


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
    provenance_summary: MemoryProvenanceSummaryRecord
    linked_entities: list[MemoryLinkedEntityRecord]
    episode_memberships: list[MemoryEventEpisodeMembershipRecord]
    supersession_relationships: list[MemoryEventSupersessionRecord]


class MemoryEpisodeDetailRecord(MemoryEpisodeRecord):
    source_lineage: list[MemoryProvenanceRecord]
    seed_basis: list[MemoryProvenanceRecord]
    membership_basis: list[MemoryProvenanceRecord]
    provenance: list[MemoryProvenanceRecord]
    provenance_summary: MemoryProvenanceSummaryRecord
    linked_events: list[MemoryEpisodeMemberRecord]


class MemoryEventProvenanceDetailRecord(BaseModel):
    event: MemoryEventRecord
    provenance: list[MemoryProvenanceRecord]
    source_lineage: list[MemoryProvenanceRecord]
    seed_basis: list[MemoryProvenanceRecord]
    provenance_summary: MemoryProvenanceSummaryRecord


class MemoryEpisodeProvenanceDetailRecord(BaseModel):
    episode: MemoryEpisodeRecord
    provenance: list[MemoryProvenanceRecord]
    source_lineage: list[MemoryProvenanceRecord]
    seed_basis: list[MemoryProvenanceRecord]
    membership_basis: list[MemoryProvenanceRecord]
    provenance_summary: MemoryProvenanceSummaryRecord


class MemoryContextQueryScopeRecord(BaseModel):
    scope_kind: str
    primary_event_id: int | None = None
    primary_episode_id: str | None = None


class MemoryContextSupersessionLinkRecord(BaseModel):
    id: str
    room_id: str
    old_event_id: str
    new_event_id: str
    reason: str | None = None
    created_at: str
    created_by_role: str


class MemoryContextCorrectionSummaryRecord(BaseModel):
    corrected_event_ids: list[int]
    corrected_episode_ids: list[str]
    rejected_event_ids: list[int]
    rejected_episode_ids: list[str]
    superseded_event_ids: list[int]
    supersession_links: list[MemoryContextSupersessionLinkRecord]


class MemoryContextPackageRecord(BaseModel):
    room_id: str
    query_scope: MemoryContextQueryScopeRecord
    included_events: list[MemoryEventDetailRecord]
    included_episodes: list[MemoryEpisodeDetailRecord]
    provenance_summary: MemoryProvenanceSummaryRecord
    correction_summary: MemoryContextCorrectionSummaryRecord
    warnings: list[str]
    limitations: list[str]
    assembly_reasoning: list[str]


class MemoryLlmContextInclusionRecord(BaseModel):
    memory_kind: MemoryOwnerType
    memory_id: str
    inclusion_reason: str


class MemoryLlmContextExclusionRecord(BaseModel):
    memory_kind: MemoryOwnerType
    memory_id: str | None = None
    exclusion_reason: str


class MemoryLlmContextPayloadRecord(BaseModel):
    room_id: str
    query_scope: MemoryContextQueryScopeRecord
    context_package: MemoryContextPackageRecord
    included_context: list[MemoryLlmContextInclusionRecord]
    excluded_context: list[MemoryLlmContextExclusionRecord]
    warnings: list[str]
    llm_call_performed: bool = False
    memory_write_enabled: bool = False
    interface_mode: str = "read_only_context"


class MemoryLlmAnswerSourceRecord(BaseModel):
    content: str
    source_refs: list[str]


class MemoryLlmAnswerRecord(BaseModel):
    room_id: str
    query_scope: MemoryContextQueryScopeRecord
    question: str
    supported: bool
    source_backed_content: list[MemoryLlmAnswerSourceRecord]
    derived_explanation: str | None = None
    uncertainty: list[str]
    limitations: list[str]
    context_payload: MemoryLlmContextPayloadRecord
    llm_call_performed: bool = False
    memory_write_enabled: bool = False
