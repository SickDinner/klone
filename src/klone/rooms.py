from dataclasses import asdict

from .contracts import ClassificationLevel
from .models import PermissionLevel, RoomCard
from .schemas import RoomRecord


ROOM_REGISTRY = [
    RoomCard(
        id="public-room",
        label="Public Room",
        room_type="public_room",
        classification="public",
        supervisor="hypervisor",
        status="active",
        allowed_agents=["hypervisor", "teacher"],
        allowed_roles=["owner", "supervisor", "evaluator"],
        retention_policy="persistent",
        permissions=["discover", "read", "summarize", "propose"],
        audit_visibility="owner_debug",
        approval_rules=["public references only", "no restricted data joins"],
    ),
    RoomCard(
        id="restricted-room",
        label="Restricted Room",
        room_type="restricted_room",
        classification="personal",
        supervisor="media supervisor",
        status="active",
        allowed_agents=["hypervisor", "media-supervisor", "ingest-worker"],
        allowed_roles=["owner", "supervisor", "worker"],
        retention_policy="persistent",
        permissions=["discover", "read", "summarize", "write", "propose"],
        audit_visibility="owner_debug",
        approval_rules=["personal assets stay local", "cross-room sharing requires supervisor summary"],
    ),
    RoomCard(
        id="sealed-room",
        label="Sealed Memory Room",
        room_type="sealed_room",
        classification="intimate",
        supervisor="memory supervisor",
        status="shell",
        allowed_agents=["hypervisor", "memory-supervisor", "teacher"],
        allowed_roles=["owner", "supervisor", "evaluator"],
        retention_policy="persistent",
        permissions=["discover", "read", "summarize", "propose", "approve"],
        audit_visibility="owner_debug",
        approval_rules=["summary-first access", "human override required for expanded access"],
    ),
    RoomCard(
        id="sandbox-room",
        label="Genomics Sandbox",
        room_type="sandbox_room",
        classification="restricted_bio",
        supervisor="genomics supervisor",
        status="shell",
        allowed_agents=["hypervisor", "genomics-supervisor"],
        allowed_roles=["owner", "supervisor"],
        retention_policy="persistent",
        permissions=["discover", "write", "summarize", "propose", "approve"],
        audit_visibility="owner_debug",
        approval_rules=["raw DNA stays sandboxed", "only supervisor-approved summaries can leave"],
    ),
    RoomCard(
        id="debug-room",
        label="Debug Room",
        room_type="debug_room",
        classification="intimate",
        supervisor="hypervisor",
        status="active",
        allowed_agents=["hypervisor", "teacher", "media-supervisor", "memory-supervisor", "genomics-supervisor"],
        allowed_roles=["owner", "debugger", "supervisor"],
        retention_policy="persistent",
        permissions=["discover", "read", "summarize", "write", "execute", "approve", "debug"],
        audit_visibility="root_only",
        approval_rules=["owner override always available", "debug traces remain visible"],
    ),
]


PERMISSION_LEVELS = [
    PermissionLevel(id="discover", description="See that a resource exists without opening raw content."),
    PermissionLevel(id="read", description="Read raw material directly."),
    PermissionLevel(id="summarize", description="Receive a bounded summary without full raw access."),
    PermissionLevel(id="write", description="Write or modify records within the room."),
    PermissionLevel(id="propose", description="Suggest actions or derived artifacts for supervisor review."),
    PermissionLevel(id="execute", description="Run jobs or workflows in the room."),
    PermissionLevel(id="approve", description="Approve gated actions or promoted summaries."),
    PermissionLevel(id="debug", description="Inspect full routing, audit, and internal state."),
]


ROOM_BY_CLASSIFICATION: dict[ClassificationLevel, str] = {
    "public": "public-room",
    "personal": "restricted-room",
    "intimate": "sealed-room",
    "restricted_bio": "sandbox-room",
}


class RoomRegistry:
    def __init__(self, rooms: list[RoomCard]) -> None:
        self._rooms = {room.id: room for room in rooms}

    def list_rooms(self) -> list[RoomRecord]:
        return [RoomRecord.model_validate(asdict(room)) for room in self._rooms.values()]

    def get_room(self, room_id: str) -> RoomRecord | None:
        room = self._rooms.get(room_id)
        if room is None:
            return None
        return RoomRecord.model_validate(asdict(room))

    def default_room_for_classification(self, classification_level: ClassificationLevel) -> RoomRecord:
        room_id = ROOM_BY_CLASSIFICATION[classification_level]
        room = self.get_room(room_id)
        if room is None:
            raise KeyError(f"Room registry is missing {room_id}")
        return room


room_registry = RoomRegistry(ROOM_REGISTRY)
