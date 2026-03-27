from typing import Literal, get_args


ClassificationLevel = Literal["public", "personal", "intimate", "restricted_bio"]
AssetKind = Literal["image", "audio", "video", "text", "document", "archive", "generic"]
IngestStatus = Literal["pending", "running", "completed", "completed_with_warnings", "failed"]
RoomStatus = Literal["active", "shell", "paused"]
ExtractionStatus = Literal["pending", "metadata_indexed", "failed"]
DedupStatus = Literal["unique", "duplicate"]
GuardDecision = Literal["allowed", "blocked", "requires_approval", "summary_only"]
RoomType = Literal["public_room", "restricted_room", "sealed_room", "sandbox_room", "debug_room"]


CLASSIFICATION_LEVEL_VALUES = set(get_args(ClassificationLevel))
ASSET_KIND_VALUES = set(get_args(AssetKind))
INGEST_STATUS_VALUES = set(get_args(IngestStatus))
ROOM_STATUS_VALUES = set(get_args(RoomStatus))
EXTRACTION_STATUS_VALUES = set(get_args(ExtractionStatus))
DEDUP_STATUS_VALUES = set(get_args(DedupStatus))
ROOM_TYPE_VALUES = set(get_args(RoomType))
