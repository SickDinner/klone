from typing import Literal, get_args


ClassificationLevel = Literal["public", "personal", "intimate", "restricted_bio"]
AssetKind = Literal["image", "audio", "video", "text", "document", "archive", "generic"]
IngestStatus = Literal["pending", "running", "completed", "completed_with_warnings", "failed"]
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


CLASSIFICATION_LEVEL_VALUES = set(get_args(ClassificationLevel))
ASSET_KIND_VALUES = set(get_args(AssetKind))
INGEST_STATUS_VALUES = set(get_args(IngestStatus))
ROOM_STATUS_VALUES = set(get_args(RoomStatus))
EXTRACTION_STATUS_VALUES = set(get_args(ExtractionStatus))
DEDUP_STATUS_VALUES = set(get_args(DedupStatus))
ROOM_TYPE_VALUES = set(get_args(RoomType))
MEMORY_ENTITY_TYPE_VALUES = set(get_args(MemoryEntityType))
MEMORY_EPISODE_TYPE_VALUES = set(get_args(MemoryEpisodeType))
MEMORY_OWNER_TYPE_VALUES = set(get_args(MemoryOwnerType))
MEMORY_PROVENANCE_TYPE_VALUES = set(get_args(MemoryProvenanceType))
MEMORY_STATUS_VALUES = set(get_args(MemoryStatus))
