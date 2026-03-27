from dataclasses import asdict, dataclass, field

from .contracts import ClassificationLevel, RoomStatus, RoomType


@dataclass(frozen=True)
class TrustZone:
    id: str
    name: str
    description: str
    examples: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ModuleCard:
    id: str
    name: str
    zone_id: ClassificationLevel
    supervisor: str
    stage: str
    status: str
    purpose: str
    key_inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AgentRole:
    id: str
    name: str
    layer: str
    responsibility: str
    watches: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class BuildPhase:
    id: str
    title: str
    goal: str
    deliverables: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RoomCard:
    id: str
    label: str
    room_type: RoomType
    classification: ClassificationLevel
    supervisor: str
    status: RoomStatus
    allowed_agents: list[str] = field(default_factory=list)
    allowed_roles: list[str] = field(default_factory=list)
    retention_policy: str = "persistent"
    permissions: list[str] = field(default_factory=list)
    audit_visibility: str = "owner_debug"
    approval_rules: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PermissionLevel:
    id: str
    description: str


@dataclass(frozen=True)
class SystemBlueprint:
    mission: str
    hypervisor_answer: str
    trust_zones: list[TrustZone]
    modules: list[ModuleCard]
    agents: list[AgentRole]
    rooms: list[RoomCard]
    permission_levels: list[PermissionLevel]
    build_phases: list[BuildPhase]

    def to_dict(self) -> dict:
        return asdict(self)
