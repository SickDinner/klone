from __future__ import annotations

from collections import Counter
from array import array
from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path

from .memory import MemoryService
from .repository import KloneRepository, utc_now_iso
from .schemas import (
    HybridBoardAxisRecord,
    HybridBoardSourceRecord,
    HybridBoardSourceTotalsRecord,
    HybridBoardSquareDetailRecord,
    HybridBoardSquareRecord,
    HybridBoardWorldMemoryClusterRefRecord,
    HybridBoardWorldMemoryNodeRefRecord,
    HybridMemoryBoardRecord,
    WorldMemoryClusterDetailRecord,
    WorldMemoryClusterRecord,
    WorldMemoryDepthJobListRecord,
    WorldMemoryDepthJobNodeRecord,
    WorldMemoryDepthJobRecord,
    WorldMemoryDepthJobRequest,
    WorldMemoryNodeDetailRecord,
    WorldMemoryNodeRecord,
    WorldMemoryPlaceViewRecord,
    WorldMemoryPlaceShellRecord,
    WorldMemoryRecord,
    WorldMemorySquareLinkRecord,
)


@dataclass(frozen=True)
class _AxisDefinition:
    id: str
    label: str
    description: str


@dataclass(frozen=True)
class _SquareSourceRef:
    source_kind: str
    source_id: str
    room_id: str
    title: str
    summary: str
    status: str | None
    occurred_at: str | None
    route_hint: str | None
    markers: tuple[str, ...]


@dataclass
class _SquareAccumulator:
    row: _AxisDefinition
    column: _AxisDefinition
    infernal_pressure: float = 0.0
    celestial_pressure: float = 0.0
    neutral_residue: float = 0.0
    scar_score: float = 0.0
    event_count: int = 0
    episode_count: int = 0
    audit_count: int = 0
    source_room_ids: set[str] = field(default_factory=set)
    markers: Counter[str] = field(default_factory=Counter)
    sources: list[_SquareSourceRef] = field(default_factory=list)
    last_touched_at: str | None = None

    def activity_score(self) -> float:
        return self.infernal_pressure + self.celestial_pressure + self.neutral_residue + self.scar_score

    def dominant_polarity(self) -> str:
        candidates = {
            "infernal": self.infernal_pressure,
            "celestial": self.celestial_pressure,
            "neutral": self.neutral_residue,
        }
        return max(candidates.items(), key=lambda item: (item[1], item[0]))[0]

    def alignment_score(self) -> float:
        total = self.infernal_pressure + self.celestial_pressure + self.neutral_residue
        if total <= 0:
            return 0.0
        return round((self.celestial_pressure - self.infernal_pressure) / total, 4)

    def update_timestamp(self, value: str | None) -> None:
        if value is None:
            return
        if self.last_touched_at is None or value > self.last_touched_at:
            self.last_touched_at = value


@dataclass(frozen=True)
class _WorldMemorySquareRef:
    square_id: str
    row_id: str
    column_id: str
    title: str
    weight: float


@dataclass(frozen=True)
class _WorldMemoryPlaceShell:
    stage: str
    eligible: bool
    depth_candidate: bool
    place_score: float
    rationale: str
    cues: tuple[str, ...]


@dataclass(frozen=True)
class _WorldMemoryNodeProjection:
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
    indexed_at: str
    fs_modified_at: str
    metadata: dict[str, object] | None
    linked_square: _WorldMemorySquareRef
    place_shell: _WorldMemoryPlaceShell


@dataclass
class _WorldMemoryClusterAccumulator:
    cluster_id: str
    room_id: str
    dataset_id: int
    dataset_label: str
    anchor_prefix: str
    label: str
    nodes: list[_WorldMemoryNodeProjection] = field(default_factory=list)
    asset_kind_counter: Counter[str] = field(default_factory=Counter)
    linked_square_weights: dict[str, float] = field(default_factory=dict)
    linked_square_refs: dict[str, _WorldMemorySquareRef] = field(default_factory=dict)
    recent_indexed_at: str | None = None

    def add_node(self, node: _WorldMemoryNodeProjection) -> None:
        self.nodes.append(node)
        self.asset_kind_counter[node.asset_kind] += 1
        self.linked_square_weights[node.linked_square.square_id] = (
            self.linked_square_weights.get(node.linked_square.square_id, 0.0) + node.linked_square.weight
        )
        self.linked_square_refs[node.linked_square.square_id] = node.linked_square
        if self.recent_indexed_at is None or node.indexed_at > self.recent_indexed_at:
            self.recent_indexed_at = node.indexed_at

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def dominant_asset_kind(self) -> str:
        if not self.asset_kind_counter:
            return "generic"
        return self.asset_kind_counter.most_common(1)[0][0]

    @property
    def place_score(self) -> float:
        if not self.nodes:
            return 0.0
        return round(sum(node.place_shell.place_score for node in self.nodes) / len(self.nodes), 4)

    @property
    def image_candidate_count(self) -> int:
        return sum(1 for node in self.nodes if node.place_shell.eligible)

    @property
    def depth_candidate_count(self) -> int:
        return sum(1 for node in self.nodes if node.place_shell.depth_candidate)

    def primary_square(self) -> _WorldMemorySquareRef | None:
        if not self.linked_square_weights:
            return None
        square_id = max(self.linked_square_weights.items(), key=lambda item: (item[1], item[0]))[0]
        return self.linked_square_refs.get(square_id)


BOARD_ROWS: tuple[_AxisDefinition, ...] = (
    _AxisDefinition("limbo", "Limbo", "Threshold states, staging, ingress, and unresolved intake."),
    _AxisDefinition("lust", "Lust", "Attraction, contact, interaction, and sensory pull."),
    _AxisDefinition("gluttony", "Gluttony", "Volume, intake appetite, corpus growth, and media accumulation."),
    _AxisDefinition("greed", "Greed", "Ownership, retention, collection, and duplicate pressure."),
    _AxisDefinition("wrath", "Wrath", "Conflict, failure, rejection, interruption, and escalation."),
    _AxisDefinition("envy", "Envy", "Comparison, contrast, ranking, and external pressure gradients."),
    _AxisDefinition("sloth", "Sloth", "Queueing, deferral, waiting, idle residue, and stalled motion."),
    _AxisDefinition("pride", "Pride", "Approval, control, doctrine, constitution, and sovereign posture."),
)

BOARD_COLUMNS: tuple[_AxisDefinition, ...] = (
    _AxisDefinition("ingress", "Ingress", "Intake, scanning, discovery, and threshold crossings."),
    _AxisDefinition("temptation", "Temptation", "Preview, recommendation, invitation, and selection pressure."),
    _AxisDefinition("possession", "Possession", "Assets, blobs, objects, attachments, and local holding."),
    _AxisDefinition("conflict", "Conflict", "Corrections, denials, clashes, and counter-moves."),
    _AxisDefinition("doctrine", "Doctrine", "Governance, constitution, rules, and formal control surfaces."),
    _AxisDefinition("mask", "Mask", "Sanitization, projection, summary-only surfaces, and public rendering."),
    _AxisDefinition("memory", "Memory", "Events, episodes, provenance, context packaging, and recall."),
    _AxisDefinition("sovereignty", "Sovereignty", "Internal runs, hypervisor posture, and system-level authority."),
)

ROW_KEYWORDS: dict[str, tuple[str, ...]] = {
    "limbo": ("ingest", "scan", "bootstrap", "discover", "preflight", "manifest", "seed", "threshold"),
    "lust": ("dialogue", "message", "conversation", "voice", "audio", "visual", "sensory", "contact"),
    "gluttony": ("dataset", "corpus", "media", "image", "video", "archive", "asset", "scene"),
    "greed": ("duplicate", "dedup", "retention", "ownership", "collection", "blob", "object", "holding"),
    "wrath": ("reject", "denied", "error", "fail", "cancel", "interrupt", "supersed", "conflict"),
    "envy": ("compare", "delta", "contrast", "diff", "relation", "ranking", "lineage"),
    "sloth": ("queue", "queued", "pending", "defer", "idle", "paused", "waiting", "staged"),
    "pride": ("constitution", "approval", "policy", "guard", "control", "hypervisor", "internal_run"),
}

COLUMN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "ingress": ("ingest", "scan", "discover", "bootstrap", "input", "manifest", "entry", "door", "gate"),
    "temptation": ("preview", "recommend", "candidate", "selection", "sample", "compare", "teaser"),
    "possession": ("asset", "blob", "object", "dataset", "attachment", "file", "archive"),
    "conflict": ("correct", "reject", "supersed", "error", "fail", "cancel", "interrupt"),
    "doctrine": ("policy", "guard", "constitution", "approval", "compliance", "permission", "governance"),
    "mask": ("summary", "sanitize", "public", "render", "output", "projection", "appearance"),
    "memory": ("memory", "event", "episode", "context", "provenance", "entity", "trace"),
    "sovereignty": ("hypervisor", "internal_run", "bootstrap", "status", "control", "runtime"),
}

POSITIVE_KEYWORDS = ("active", "approved", "completed", "available", "provenance", "context", "governance", "constitution")
NEGATIVE_KEYWORDS = ("rejected", "superseded", "failed", "cancelled", "interrupted", "denied", "error", "conflict")
NEUTRAL_KEYWORDS = ("queued", "pending", "preview", "sample", "staging", "idle")
SCAR_KEYWORDS = ("correct", "supersed", "duplicate", "interrupt", "rejected", "error")

SCENE_KEYWORDS: tuple[str, ...] = (
    "door", "room", "hall", "corridor", "tunnel", "gate", "window", "stair", "stairs",
    "chamber", "street", "house", "tower", "church", "station", "garden", "forest",
    "city", "beach", "lake", "landscape", "scene", "bathroom", "kitchen", "bedroom",
)


def _row_axes() -> list[HybridBoardAxisRecord]:
    return [
        HybridBoardAxisRecord(id=row.id, index=index, label=row.label, description=row.description)
        for index, row in enumerate(BOARD_ROWS)
    ]


def _column_axes() -> list[HybridBoardAxisRecord]:
    return [
        HybridBoardAxisRecord(id=column.id, index=index, label=column.label, description=column.description)
        for index, column in enumerate(BOARD_COLUMNS)
    ]


def _normalize_text(values: list[object]) -> str:
    return " ".join(str(value).strip().lower() for value in values if value is not None and str(value).strip())


def _normalize_marker(value: object) -> str | None:
    text = str(value).strip().lower() if value is not None else ""
    return text or None


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _truncate(value: str, limit: int) -> str:
    text = value.strip()
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1].rstrip()}…"


def _pick_axis(
    *,
    definitions: tuple[_AxisDefinition, ...],
    keyword_map: dict[str, tuple[str, ...]],
    text: str,
    seed: str,
) -> _AxisDefinition:
    best_score = -1
    best_definition: _AxisDefinition | None = None
    for definition in definitions:
        score = sum(text.count(keyword) for keyword in keyword_map[definition.id])
        if score > best_score:
            best_score = score
            best_definition = definition
    if best_definition is None:
        return definitions[0]
    if best_score > 0:
        return best_definition
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    return definitions[digest[0] % len(definitions)]


def _decode_metadata_json(raw: object) -> dict[str, object] | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _decode_string_list(raw: object) -> list[str]:
    if not isinstance(raw, str) or not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    return [str(item) for item in payload]


def _asset_content_route(asset_id: int) -> str:
    return f"/api/assets/{asset_id}/content"


def _depth_preview_route(job_id: int, node_id: str) -> str:
    return f"/api/simulation/world-memory/depth/jobs/{job_id}/nodes/{node_id}/preview"


def _depth_raw_route(job_id: int, node_id: str) -> str:
    return f"/api/simulation/world-memory/depth/jobs/{job_id}/nodes/{node_id}/raw"


class HybridMemoryBoardService:
    PROJECTION_VERSION = "hybrid_memory_board.v1"
    DEFAULT_PER_ROOM_LIMIT = 64

    def __init__(self, repository: KloneRepository) -> None:
        self.repository = repository
        self.memory_service = MemoryService(repository)

    def build_board(
        self,
        *,
        room_ids: list[str],
        requested_room_id: str | None = None,
        per_room_limit: int = DEFAULT_PER_ROOM_LIMIT,
    ) -> HybridMemoryBoardRecord:
        resolved_room_ids, accumulators, source_totals = self._project_board(
            room_ids=room_ids,
            per_room_limit=per_room_limit,
        )
        squares = self._build_square_records(accumulators)
        notes, warnings = self._projection_notes(source_totals)
        return HybridMemoryBoardRecord(
            projection_version=self.PROJECTION_VERSION,
            read_only=True,
            requested_room_id=requested_room_id,
            resolved_room_ids=resolved_room_ids,
            square_count=len(squares),
            source_totals=HybridBoardSourceTotalsRecord(**source_totals),
            row_axes=_row_axes(),
            column_axes=_column_axes(),
            squares=squares,
            notes=notes,
            warnings=warnings,
        )

    def build_square_detail(
        self,
        *,
        room_ids: list[str],
        requested_room_id: str | None,
        row_id: str,
        column_id: str,
        per_room_limit: int = DEFAULT_PER_ROOM_LIMIT,
        source_limit: int = 18,
    ) -> HybridBoardSquareDetailRecord:
        resolved_room_ids, accumulators, source_totals = self._project_board(
            room_ids=room_ids,
            per_room_limit=per_room_limit,
        )
        if (row_id, column_id) not in accumulators:
            raise ValueError(f"Unknown hybrid board square {row_id}:{column_id}.")

        square_records = {square.square_id: square for square in self._build_square_records(accumulators)}
        square = square_records[f"{row_id}:{column_id}"]
        sources = sorted(
            accumulators[(row_id, column_id)].sources,
            key=lambda item: ((item.occurred_at or ""), item.source_id),
            reverse=True,
        )[:source_limit]

        world_memory_service = WorldMemoryService(self.repository)
        _, _, cluster_accumulators = world_memory_service._project_world_memory(
            room_ids=room_ids,
            per_room_limit=WorldMemoryService.DEFAULT_PER_ROOM_LIMIT,
        )
        linked_cluster_accumulators = [
            cluster
            for cluster in cluster_accumulators.values()
            if any(node.linked_square.square_id == square.square_id for node in cluster.nodes)
        ]
        linked_cluster_accumulators.sort(
            key=lambda cluster: (
                -sum(1 for node in cluster.nodes if node.linked_square.square_id == square.square_id),
                -cluster.place_score,
                cluster.cluster_id,
            )
        )
        linked_clusters = [
            HybridBoardWorldMemoryClusterRefRecord(
                cluster_id=cluster.cluster_id,
                room_id=cluster.room_id,
                dataset_label=cluster.dataset_label,
                label=cluster.label,
                node_count=cluster.node_count,
                dominant_asset_kind=cluster.dominant_asset_kind,
                primary_square_id=(cluster.primary_square().square_id if cluster.primary_square() else None),
                primary_square_title=(cluster.primary_square().title if cluster.primary_square() else None),
                place_score=cluster.place_score,
            )
            for cluster in linked_cluster_accumulators[:6]
        ]

        linked_nodes = [
            HybridBoardWorldMemoryNodeRefRecord(
                node_id=node.node_id,
                cluster_id=node.cluster_id,
                room_id=node.room_id,
                label=node.label,
                anchor_type=node.anchor_type,
                asset_kind=node.asset_kind,
                primary_square_id=node.linked_square.square_id,
                primary_square_title=node.linked_square.title,
                place_score=node.place_shell.place_score,
                depth_candidate=node.place_shell.depth_candidate,
            )
            for cluster in linked_cluster_accumulators
            for node in cluster.nodes
            if node.linked_square.square_id == square.square_id
        ]
        linked_nodes.sort(key=lambda item: (-item.place_score, item.node_id))

        notes, warnings = self._projection_notes(source_totals)
        notes = [
            *notes,
            "Square detail lists source slices that contributed pressure to this board position.",
            "Linked world-memory anchors use the same square taxonomy so place-memory and board pressure stay readable together.",
        ]
        return HybridBoardSquareDetailRecord(
            projection_version=self.PROJECTION_VERSION,
            read_only=True,
            requested_room_id=requested_room_id,
            resolved_room_ids=resolved_room_ids,
            row_axes=_row_axes(),
            column_axes=_column_axes(),
            square=square,
            source_count=len(accumulators[(row_id, column_id)].sources),
            sources=[
                HybridBoardSourceRecord(
                    source_kind=item.source_kind,
                    source_id=item.source_id,
                    room_id=item.room_id,
                    title=item.title,
                    summary=item.summary,
                    status=item.status,
                    occurred_at=item.occurred_at,
                    route_hint=item.route_hint,
                    markers=list(item.markers),
                )
                for item in sources
            ],
            linked_cluster_count=len(linked_clusters),
            linked_node_count=len(linked_nodes),
            linked_clusters=linked_clusters,
            linked_nodes=linked_nodes[:10],
            notes=notes,
            warnings=warnings,
        )

    def _project_board(
        self,
        *,
        room_ids: list[str],
        per_room_limit: int,
    ) -> tuple[list[str], dict[tuple[str, str], _SquareAccumulator], dict[str, int]]:
        resolved_room_ids = sorted(dict.fromkeys(room_ids))
        accumulators = {
            (row.id, column.id): _SquareAccumulator(row=row, column=column)
            for row in BOARD_ROWS
            for column in BOARD_COLUMNS
        }
        source_totals = {"memory_events": 0, "memory_episodes": 0, "audit_events": 0}

        for room_id in resolved_room_ids:
            audit_rows = self.repository.list_audit_events(room_id=room_id, limit=per_room_limit)
            for row in audit_rows:
                source_totals["audit_events"] += 1
                title = str(row.get("event_type") or "audit_event")
                summary = str(row.get("summary") or title)
                self._apply_source(
                    accumulators=accumulators,
                    source_kind="audit",
                    source_id=f"audit:{row['id']}",
                    room_id=room_id,
                    tokens=[
                        row.get("event_type"),
                        row.get("target_type"),
                        row.get("classification_level"),
                        row.get("summary"),
                    ],
                    status=None,
                    markers=[row.get("event_type"), row.get("target_type"), row.get("classification_level")],
                    touched_at=row.get("created_at"),
                    title=title,
                    summary=summary,
                    route_hint=f"/api/audit?room_id={room_id}",
                )

            event_rows = self.memory_service.query_events(
                room_id=room_id,
                limit=per_room_limit,
                offset=0,
                include_corrected=True,
            )
            for row in event_rows:
                source_totals["memory_events"] += 1
                self._apply_source(
                    accumulators=accumulators,
                    source_kind="memory_event",
                    source_id=f"memory_event:{row['id']}",
                    room_id=room_id,
                    tokens=[
                        row.get("event_type"),
                        row.get("source_table"),
                        row.get("classification_level"),
                        row.get("status"),
                        row.get("title"),
                        row.get("correction_reason"),
                    ],
                    status=row.get("status"),
                    markers=[row.get("event_type"), row.get("status"), row.get("classification_level")],
                    touched_at=row.get("updated_at") or row.get("occurred_at"),
                    title=str(row.get("title") or row.get("event_type") or f"event {row['id']}"),
                    summary=str(row.get("evidence_text") or row.get("title") or ""),
                    route_hint=f"/api/memory/events/{row['id']}?room_id={room_id}",
                )

            episode_rows = self.memory_service.query_episodes(
                room_id=room_id,
                limit=per_room_limit,
                offset=0,
                include_corrected=True,
            )
            for row in episode_rows:
                source_totals["memory_episodes"] += 1
                self._apply_source(
                    accumulators=accumulators,
                    source_kind="memory_episode",
                    source_id=f"memory_episode:{row['id']}",
                    room_id=room_id,
                    tokens=[
                        row.get("episode_type"),
                        row.get("grouping_basis"),
                        row.get("source_table"),
                        row.get("classification_level"),
                        row.get("status"),
                        row.get("title"),
                        row.get("correction_reason"),
                    ],
                    status=row.get("status"),
                    markers=[row.get("episode_type"), row.get("status"), row.get("classification_level")],
                    touched_at=row.get("updated_at") or row.get("end_at"),
                    title=str(row.get("title") or row.get("episode_type") or f"episode {row['id']}"),
                    summary=str(row.get("summary") or row.get("title") or ""),
                    route_hint=f"/api/memory/episodes/{row['id']}?room_id={room_id}",
                )
        return resolved_room_ids, accumulators, source_totals

    def _build_square_records(
        self,
        accumulators: dict[tuple[str, str], _SquareAccumulator],
    ) -> list[HybridBoardSquareRecord]:
        max_activity = max((acc.activity_score() for acc in accumulators.values()), default=0.0)
        denominator = max(max_activity, 1.0)
        squares: list[HybridBoardSquareRecord] = []
        for row_index, row in enumerate(BOARD_ROWS):
            for column_index, column in enumerate(BOARD_COLUMNS):
                acc = accumulators[(row.id, column.id)]
                activity_score = round(acc.activity_score(), 4)
                squares.append(
                    HybridBoardSquareRecord(
                        square_id=f"{row.id}:{column.id}",
                        row_id=row.id,
                        row_index=row_index,
                        column_id=column.id,
                        column_index=column_index,
                        title=f"{row.label} x {column.label}",
                        dominant_polarity=acc.dominant_polarity(),
                        infernal_pressure=round(acc.infernal_pressure, 4),
                        celestial_pressure=round(acc.celestial_pressure, 4),
                        neutral_residue=round(acc.neutral_residue, 4),
                        scar_score=round(acc.scar_score, 4),
                        activity_score=activity_score,
                        intensity=round(activity_score / denominator, 4),
                        alignment_score=acc.alignment_score(),
                        signal_count=acc.event_count + acc.episode_count + acc.audit_count,
                        event_count=acc.event_count,
                        episode_count=acc.episode_count,
                        audit_count=acc.audit_count,
                        source_room_ids=sorted(acc.source_room_ids),
                        top_markers=[item for item, _ in acc.markers.most_common(3)],
                        last_touched_at=acc.last_touched_at,
                    )
                )
        return squares

    def _apply_source(
        self,
        *,
        accumulators: dict[tuple[str, str], _SquareAccumulator],
        source_kind: str,
        source_id: str,
        room_id: str,
        tokens: list[object],
        status: object,
        markers: list[object],
        touched_at: str | None,
        title: str,
        summary: str,
        route_hint: str | None,
    ) -> None:
        text = _normalize_text(tokens)
        row = _pick_axis(definitions=BOARD_ROWS, keyword_map=ROW_KEYWORDS, text=text, seed=f"row:{source_kind}:{source_id}")
        column = _pick_axis(
            definitions=BOARD_COLUMNS,
            keyword_map=COLUMN_KEYWORDS,
            text=text,
            seed=f"column:{source_kind}:{source_id}",
        )
        acc = accumulators[(row.id, column.id)]

        base_weight = {"audit": 1.0, "memory_event": 1.35, "memory_episode": 1.15}[source_kind]
        normalized_status = str(status or "").strip().lower()

        infernal = 0.0
        celestial = 0.0
        neutral = base_weight * 0.35
        scar = 0.0

        if _contains_any(text, NEGATIVE_KEYWORDS):
            infernal += base_weight * 1.1
            scar += base_weight * 0.55
        if normalized_status in {"rejected", "superseded"}:
            infernal += base_weight * 1.4
            scar += base_weight * 0.9
        if normalized_status in {"active", "completed"}:
            celestial += base_weight * 0.95
        if _contains_any(text, POSITIVE_KEYWORDS):
            celestial += base_weight * 0.85
        if _contains_any(text, NEUTRAL_KEYWORDS):
            neutral += base_weight * 0.65
        if _contains_any(text, SCAR_KEYWORDS):
            scar += base_weight * 0.45
        if infernal == 0.0 and celestial == 0.0:
            neutral += base_weight * 0.45

        acc.infernal_pressure += infernal
        acc.celestial_pressure += celestial
        acc.neutral_residue += neutral
        acc.scar_score += scar
        acc.source_room_ids.add(room_id)
        acc.update_timestamp(touched_at)

        if source_kind == "audit":
            acc.audit_count += 1
        elif source_kind == "memory_event":
            acc.event_count += 1
        else:
            acc.episode_count += 1

        normalized_markers = [normalized for marker in markers if (normalized := _normalize_marker(marker))]
        for marker in normalized_markers:
            acc.markers[marker] += 1
        acc.sources.append(
            _SquareSourceRef(
                source_kind=source_kind,
                source_id=source_id,
                room_id=room_id,
                title=title,
                summary=_truncate(summary, 220),
                status=normalized_status or None,
                occurred_at=touched_at,
                route_hint=route_hint,
                markers=tuple(normalized_markers[:5]),
            )
        )

    def _projection_notes(self, source_totals: dict[str, int]) -> tuple[list[str], list[str]]:
        notes = [
            "This board is a governed read-only projection over audit, memory events, and memory episodes.",
            "Mythic labels are runtime surfaces only; the existing audit and memory records remain source truth.",
            "Square pressure is deterministic and derived from typed system evidence, not from hidden model state.",
        ]
        warnings: list[str] = []
        if sum(source_totals.values()) == 0:
            warnings.append("No audit or memory sources were available for this board projection yet.")
        return notes, warnings


class WorldMemoryService:
    PROJECTION_VERSION = "world_memory.v1"
    DEFAULT_PER_ROOM_LIMIT = 48

    def __init__(self, repository: KloneRepository) -> None:
        self.repository = repository

    def build_world_memory(
        self,
        *,
        room_ids: list[str],
        requested_room_id: str | None = None,
        per_room_limit: int = DEFAULT_PER_ROOM_LIMIT,
    ) -> WorldMemoryRecord:
        resolved_room_ids, node_projections, cluster_accumulators = self._project_world_memory(
            room_ids=room_ids,
            per_room_limit=per_room_limit,
        )
        node_records = [self._node_record_from_projection(node) for node in node_projections]
        cluster_records = [self._cluster_record_from_accumulator(cluster) for cluster in cluster_accumulators.values()]
        cluster_records.sort(key=lambda item: (-item.node_count, item.cluster_id))
        notes, warnings = self._projection_notes(node_records)
        return WorldMemoryRecord(
            projection_version=self.PROJECTION_VERSION,
            read_only=True,
            requested_room_id=requested_room_id,
            resolved_room_ids=resolved_room_ids,
            node_count=len(node_records),
            cluster_count=len(cluster_records),
            place_candidate_count=sum(1 for node in node_records if node.place_score > 0),
            depth_candidate_count=sum(1 for node in node_records if node.depth_candidate),
            anchor_types=sorted({node.anchor_type for node in node_records}),
            clusters=cluster_records,
            nodes=node_records[:72],
            notes=notes,
            warnings=warnings,
        )

    def build_cluster_detail(
        self,
        *,
        room_ids: list[str],
        requested_room_id: str | None,
        cluster_id: str,
        per_room_limit: int = DEFAULT_PER_ROOM_LIMIT,
    ) -> WorldMemoryClusterDetailRecord:
        resolved_room_ids, _, cluster_accumulators = self._project_world_memory(
            room_ids=room_ids,
            per_room_limit=per_room_limit,
        )
        cluster = cluster_accumulators.get(cluster_id)
        if cluster is None:
            raise ValueError(f"World-memory cluster {cluster_id} was not found.")
        linked_squares = sorted(
            cluster.linked_square_refs.values(),
            key=lambda ref: (-cluster.linked_square_weights.get(ref.square_id, 0.0), ref.square_id),
        )
        notes = [
            "Cluster detail groups nearby asset anchors under one governed place shell.",
            "Linked squares expose where this cluster currently touches the simulation board taxonomy.",
        ]
        return WorldMemoryClusterDetailRecord(
            projection_version=self.PROJECTION_VERSION,
            read_only=True,
            requested_room_id=requested_room_id,
            resolved_room_ids=resolved_room_ids,
            cluster=self._cluster_record_from_accumulator(cluster),
            linked_squares=[
                WorldMemorySquareLinkRecord(
                    square_id=ref.square_id,
                    row_id=ref.row_id,
                    column_id=ref.column_id,
                    title=ref.title,
                    weight=round(cluster.linked_square_weights.get(ref.square_id, ref.weight), 4),
                )
                for ref in linked_squares[:6]
            ],
            nodes=[self._node_record_from_projection(node) for node in cluster.nodes[:18]],
            notes=notes,
            warnings=[],
        )

    def build_node_detail(
        self,
        *,
        room_ids: list[str],
        requested_room_id: str | None,
        node_id: str,
        per_room_limit: int = DEFAULT_PER_ROOM_LIMIT,
    ) -> WorldMemoryNodeDetailRecord:
        resolved_room_ids, node_projections, _ = self._project_world_memory(
            room_ids=room_ids,
            per_room_limit=per_room_limit,
        )
        node = next((item for item in node_projections if item.node_id == node_id), None)
        if node is None:
            raise ValueError(f"World-memory node {node_id} was not found.")
        notes = [
            "Node detail is a governed shell for one indexed local asset anchor.",
            "Place shell values are deterministic heuristics for later depth and spatial reconstruction, not a latent 3D model.",
        ]
        return WorldMemoryNodeDetailRecord(
            projection_version=self.PROJECTION_VERSION,
            read_only=True,
            requested_room_id=requested_room_id,
            resolved_room_ids=resolved_room_ids,
            node=self._node_record_from_projection(node),
            linked_square=WorldMemorySquareLinkRecord(
                square_id=node.linked_square.square_id,
                row_id=node.linked_square.row_id,
                column_id=node.linked_square.column_id,
                title=node.linked_square.title,
                weight=node.linked_square.weight,
            ),
            place_shell=WorldMemoryPlaceShellRecord(
                stage=node.place_shell.stage,
                eligible=node.place_shell.eligible,
                depth_candidate=node.place_shell.depth_candidate,
                place_score=node.place_shell.place_score,
                rationale=node.place_shell.rationale,
                cues=list(node.place_shell.cues),
            ),
            metadata=node.metadata,
            notes=notes,
            warnings=[],
        )

    def _project_world_memory(
        self,
        *,
        room_ids: list[str],
        per_room_limit: int,
    ) -> tuple[list[str], list[_WorldMemoryNodeProjection], dict[str, _WorldMemoryClusterAccumulator]]:
        resolved_room_ids = sorted(dict.fromkeys(room_ids))
        node_rows: list[dict[str, object]] = []
        max_size = 1

        for room_id in resolved_room_ids:
            assets = self.repository.list_assets(room_id=room_id, limit=per_room_limit)
            datasets = {dataset["id"]: dataset for dataset in self.repository.list_datasets(room_id=room_id)}
            for row in assets:
                dataset = datasets.get(row["dataset_id"], {})
                size_bytes = int(row.get("size_bytes") or 0)
                max_size = max(max_size, size_bytes)
                relative_path = str(row.get("relative_path") or row.get("file_name") or "")
                normalized_path = relative_path.replace("\\", "/")
                path_parts = [part for part in normalized_path.split("/") if part]
                anchor_prefix = path_parts[0] if path_parts else "."
                asset_kind = str(row.get("asset_kind") or "generic")
                anchor_type = self._anchor_type_for_asset_kind(asset_kind)
                cluster_id = f"{room_id}:{row['dataset_id']}:{anchor_prefix}:{anchor_type}"
                node_rows.append(
                    {
                        "node_id": f"asset:{row['id']}",
                        "cluster_id": cluster_id,
                        "room_id": room_id,
                        "dataset_id": int(row["dataset_id"]),
                        "dataset_label": str(row.get("dataset_label") or dataset.get("label") or f"dataset {row['dataset_id']}"),
                        "asset_id": int(row["id"]),
                        "asset_kind": asset_kind,
                        "anchor_type": anchor_type,
                        "label": self._asset_label(row),
                        "relative_path": relative_path,
                        "file_name": str(row.get("file_name") or ""),
                        "size_bytes": size_bytes,
                        "indexed_at": str(row.get("indexed_at") or ""),
                        "fs_modified_at": str(row.get("fs_modified_at") or ""),
                        "anchor_prefix": anchor_prefix,
                        "metadata": _decode_metadata_json(row.get("metadata_json")),
                    }
                )

        projections: list[_WorldMemoryNodeProjection] = []
        clusters: dict[str, _WorldMemoryClusterAccumulator] = {}

        for index, row in enumerate(sorted(node_rows, key=lambda item: (str(item["indexed_at"]), str(item["node_id"])), reverse=True)):
            intensity = self._node_intensity(size_bytes=int(row["size_bytes"]), max_size=max_size, index=index)
            place_shell = self._build_place_shell(row)
            linked_square = self._project_square_for_node(row=row, place_shell=place_shell, intensity=intensity)
            projection = _WorldMemoryNodeProjection(
                node_id=str(row["node_id"]),
                cluster_id=str(row["cluster_id"]),
                room_id=str(row["room_id"]),
                dataset_id=int(row["dataset_id"]),
                dataset_label=str(row["dataset_label"]),
                asset_id=int(row["asset_id"]),
                asset_kind=str(row["asset_kind"]),
                anchor_type=str(row["anchor_type"]),
                label=str(row["label"]),
                relative_path=str(row["relative_path"]),
                file_name=str(row["file_name"]),
                size_bytes=int(row["size_bytes"]),
                intensity=intensity,
                indexed_at=str(row["indexed_at"]),
                fs_modified_at=str(row["fs_modified_at"]),
                metadata=row.get("metadata") if isinstance(row.get("metadata"), dict) else None,
                linked_square=linked_square,
                place_shell=place_shell,
            )
            projections.append(projection)

            cluster = clusters.get(projection.cluster_id)
            if cluster is None:
                cluster = _WorldMemoryClusterAccumulator(
                    cluster_id=projection.cluster_id,
                    room_id=projection.room_id,
                    dataset_id=projection.dataset_id,
                    dataset_label=projection.dataset_label,
                    anchor_prefix=str(row["anchor_prefix"]),
                    label=self._cluster_label(projection.dataset_label, str(row["anchor_prefix"]), projection.anchor_type),
                )
                clusters[projection.cluster_id] = cluster
            cluster.add_node(projection)

        projections.sort(key=lambda item: (item.indexed_at, item.node_id), reverse=True)
        return resolved_room_ids, projections, clusters

    def _build_place_shell(self, row: dict[str, object]) -> _WorldMemoryPlaceShell:
        asset_kind = str(row["asset_kind"])
        text = " ".join(
            [
                asset_kind,
                str(row["relative_path"]).lower(),
                str(row["file_name"]).lower(),
                str(row["dataset_label"]).lower(),
                str(row["anchor_prefix"]).lower(),
                str(row["anchor_type"]),
            ]
        )
        detected_keywords = [keyword for keyword in SCENE_KEYWORDS if keyword in text]
        hierarchical_bonus = 0.06 if str(row["anchor_prefix"]).lower() not in {"", "."} else 0.0
        keyword_bonus = min(0.28, len(detected_keywords) * 0.07)

        if asset_kind == "image":
            base_score = 0.56
            stage = "depth_anything_v2_candidate"
            eligible = True
            depth_candidate = True
            rationale = "Indexed image asset can seed monocular depth and 2.5D place reconstruction later."
        elif asset_kind == "video":
            base_score = 0.48
            stage = "multiframe_scene_candidate"
            eligible = True
            depth_candidate = False
            rationale = "Indexed video asset can seed later multi-frame place shells, but no depth pass is run yet."
        elif asset_kind in {"document", "audio"}:
            base_score = 0.22
            stage = "trace_only"
            eligible = False
            depth_candidate = False
            rationale = "This asset stays as a trace anchor only; it does not yet seed a spatial depth shell."
        else:
            base_score = 0.18
            stage = "trace_only"
            eligible = False
            depth_candidate = False
            rationale = "This asset remains a governed trace without depth or place reconstruction."

        metadata = row.get("metadata")
        cues = [f"kind:{asset_kind}", f"anchor:{row['anchor_type']}", *(f"scene:{keyword}" for keyword in detected_keywords[:4])]
        if isinstance(metadata, dict):
            root_path = metadata.get("root_path")
            if isinstance(root_path, str) and root_path:
                cues.append("source:recursive_file_scan")

        return _WorldMemoryPlaceShell(
            stage=stage,
            eligible=eligible,
            depth_candidate=depth_candidate,
            place_score=round(min(1.0, base_score + hierarchical_bonus + keyword_bonus), 4),
            rationale=rationale,
            cues=tuple(cues[:8]),
        )

    def _project_square_for_node(
        self,
        *,
        row: dict[str, object],
        place_shell: _WorldMemoryPlaceShell,
        intensity: float,
    ) -> _WorldMemorySquareRef:
        text = _normalize_text(
            [
                row["asset_kind"],
                row["anchor_type"],
                row["relative_path"],
                row["dataset_label"],
                row["anchor_prefix"],
                place_shell.stage,
                *place_shell.cues,
            ]
        )
        row_axis = _pick_axis(
            definitions=BOARD_ROWS,
            keyword_map=ROW_KEYWORDS,
            text=text,
            seed=f"world-row:{row['node_id']}",
        )
        column_axis = _pick_axis(
            definitions=BOARD_COLUMNS,
            keyword_map=COLUMN_KEYWORDS,
            text=text,
            seed=f"world-column:{row['node_id']}",
        )
        return _WorldMemorySquareRef(
            square_id=f"{row_axis.id}:{column_axis.id}",
            row_id=row_axis.id,
            column_id=column_axis.id,
            title=f"{row_axis.label} x {column_axis.label}",
            weight=round(min(1.0, (place_shell.place_score * 0.7) + (intensity * 0.3)), 4),
        )

    def _cluster_record_from_accumulator(self, cluster: _WorldMemoryClusterAccumulator) -> WorldMemoryClusterRecord:
        primary_square = cluster.primary_square()
        return WorldMemoryClusterRecord(
            cluster_id=cluster.cluster_id,
            room_id=cluster.room_id,
            dataset_id=cluster.dataset_id,
            dataset_label=cluster.dataset_label,
            anchor_prefix=cluster.anchor_prefix,
            label=cluster.label,
            node_count=cluster.node_count,
            dominant_asset_kind=cluster.dominant_asset_kind,
            primary_square_id=primary_square.square_id if primary_square else None,
            primary_square_title=primary_square.title if primary_square else None,
            place_score=cluster.place_score,
            image_candidate_count=cluster.image_candidate_count,
            depth_candidate_count=cluster.depth_candidate_count,
            recent_indexed_at=cluster.recent_indexed_at,
        )

    def _node_record_from_projection(self, node: _WorldMemoryNodeProjection) -> WorldMemoryNodeRecord:
        return WorldMemoryNodeRecord(
            node_id=node.node_id,
            cluster_id=node.cluster_id,
            room_id=node.room_id,
            dataset_id=node.dataset_id,
            dataset_label=node.dataset_label,
            asset_id=node.asset_id,
            asset_kind=node.asset_kind,
            anchor_type=node.anchor_type,
            label=node.label,
            relative_path=node.relative_path,
            file_name=node.file_name,
            size_bytes=node.size_bytes,
            intensity=node.intensity,
            primary_square_id=node.linked_square.square_id,
            primary_square_title=node.linked_square.title,
            place_score=node.place_shell.place_score,
            depth_candidate=node.place_shell.depth_candidate,
            indexed_at=node.indexed_at,
            fs_modified_at=node.fs_modified_at,
        )

    def _projection_notes(self, node_records: list[WorldMemoryNodeRecord]) -> tuple[list[str], list[str]]:
        notes = [
            "World Memory v1 is a governed asset-anchor shell, not a 3D reconstruction engine yet.",
            "Nodes are derived from indexed local assets and grouped into deterministic clusters by room, dataset, and path prefix.",
            "Image anchors expose a depth/place candidate shell so later monocular depth and 2.5D scene work has a governed starting surface.",
        ]
        warnings: list[str] = []
        if not node_records:
            warnings.append("No indexed assets were available to build the world-memory shell yet.")
        elif not any(node.depth_candidate for node in node_records):
            warnings.append("No image anchors are available for depth/place candidates yet.")
        return notes, warnings

    def _node_intensity(self, *, size_bytes: int, max_size: int, index: int) -> float:
        size_component = math.sqrt(size_bytes / max_size) if max_size > 0 else 0.0
        recency_component = max(0.12, 1.0 - (index * 0.02))
        return round(min(1.0, (size_component * 0.65) + (recency_component * 0.35)), 4)

    @staticmethod
    def _anchor_type_for_asset_kind(asset_kind: str) -> str:
        return {
            "image": "image_scene",
            "video": "video_scene",
            "audio": "audio_trace",
            "document": "document_trace",
            "archive": "archive_mass",
        }.get(asset_kind, "generic_trace")

    @staticmethod
    def _asset_label(row: dict[str, object]) -> str:
        relative_path = str(row.get("relative_path") or row.get("file_name") or "")
        return relative_path.replace("\\", " / ")

    @staticmethod
    def _cluster_label(dataset_label: str, anchor_prefix: str, anchor_type: str) -> str:
        if anchor_prefix == ".":
            return f"{dataset_label} / root / {anchor_type}"
        return f"{dataset_label} / {anchor_prefix} / {anchor_type}"
