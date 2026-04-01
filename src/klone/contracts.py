from typing import Literal, get_args


APP_VERSION = "0.2.0"
BOOTSTRAP_VERSION = "b00.1"
SCHEMA_VERSION = "w1_4_world_memory_place_shell"
SCHEMA_USER_VERSION = 205
MODULE_REGISTRY_VERSION = "system_blueprint_v1"
SYSTEM_SCOPE_ID = "system"
BOOTSTRAP_TASK_ID = "task:bootstrap:system_startup"


ClassificationLevel = Literal["public", "personal", "intimate", "restricted_bio"]
AssetKind = Literal["image", "audio", "video", "text", "document", "archive", "generic"]
IngestStatus = Literal["pending", "running", "completed", "completed_with_warnings", "failed"]
IngestQueueStatus = Literal["queued", "running", "interrupted", "completed", "failed", "cancelled"]
RoomStatus = Literal["active", "shell", "paused"]
ExtractionStatus = Literal["pending", "metadata_indexed", "failed"]
DedupStatus = Literal["unique", "duplicate"]
GuardDecision = Literal["allowed", "blocked", "requires_approval", "summary_only"]
RoomType = Literal["public_room", "restricted_room", "sealed_room", "sandbox_room", "debug_room"]
MemoryEntityType = Literal["dataset", "room", "system_actor"]
MemoryEpisodeType = Literal["system_ingest_run"]
MemoryOwnerType = Literal["event", "episode"]
MemoryProvenanceType = Literal["source_lineage", "seed_basis", "membership_basis"]
MemoryStatus = Literal["active", "rejected", "superseded"]
InternalRunKind = Literal["bootstrap"]
InternalRunStatus = Literal["running", "completed", "failed", "blocked"]
InternalRunTrigger = Literal["startup"]


CLASSIFICATION_LEVEL_VALUES = set(get_args(ClassificationLevel))
ASSET_KIND_VALUES = set(get_args(AssetKind))
INGEST_STATUS_VALUES = set(get_args(IngestStatus))
INGEST_QUEUE_STATUS_VALUES = set(get_args(IngestQueueStatus))
ROOM_STATUS_VALUES = set(get_args(RoomStatus))
EXTRACTION_STATUS_VALUES = set(get_args(ExtractionStatus))
DEDUP_STATUS_VALUES = set(get_args(DedupStatus))
ROOM_TYPE_VALUES = set(get_args(RoomType))
MEMORY_ENTITY_TYPE_VALUES = set(get_args(MemoryEntityType))
MEMORY_EPISODE_TYPE_VALUES = set(get_args(MemoryEpisodeType))
MEMORY_OWNER_TYPE_VALUES = set(get_args(MemoryOwnerType))
MEMORY_PROVENANCE_TYPE_VALUES = set(get_args(MemoryProvenanceType))
MEMORY_STATUS_VALUES = set(get_args(MemoryStatus))
INTERNAL_RUN_KIND_VALUES = set(get_args(InternalRunKind))
INTERNAL_RUN_STATUS_VALUES = set(get_args(InternalRunStatus))
INTERNAL_RUN_TRIGGER_VALUES = set(get_args(InternalRunTrigger))
