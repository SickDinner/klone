from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
import hashlib
import math

from .memory import MemoryService
from .repository import KloneRepository
from .schemas import (
    HybridBoardAxisRecord,
    HybridBoardSourceRecord,
    HybridBoardSourceTotalsRecord,
    HybridBoardSquareDetailRecord,
    HybridBoardSquareRecord,
    HybridMemoryBoardRecord,
    WorldMemoryClusterRecord,
    WorldMemoryNodeRecord,
    WorldMemoryRecord,
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
    "limbo": ("ingest", "scan", "bootstrap", "discover", "preflight", "manifest", "seed"),
    "lust": ("dialogue", "message", "conversation", "voice", "audio", "visual", "sensory"),
    "gluttony": ("dataset", "corpus", "media", "image", "video", "archive", "asset"),
    "greed": ("duplicate", "dedup", "retention", "ownership", "collection", "blob", "object"),
    "wrath": ("reject", "denied", "error", "fail", "cancel", "interrupt", "supersed", "conflict"),
    "envy": ("compare", "delta", "contrast", "diff", "relation", "ranking", "lineage"),
    "sloth": ("queue", "queued", "pending", "defer", "idle", "paused", "waiting"),
    "pride": ("constitution", "approval", "policy", "guard", "control", "hypervisor", "internal_run"),
}

COLUMN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "ingress": ("ingest", "scan", "discover", "bootstrap", "input", "manifest"),
    "temptation": ("preview", "recommend", "candidate", "selection", "sample", "compare"),
    "possession": ("asset", "blob", "object", "dataset", "attachment", "file"),
    "conflict": ("correct", "reject", "supersed", "error", "fail", "cancel", "interrupt"),
    "doctrine": ("policy", "guard", "constitution", "approval", "compliance", "permission"),
    "mask": ("summary", "sanitize", "public", "render", "output", "projection"),
    "memory": ("memory", "event", "episode", "context", "provenance", "entity"),
    "sovereignty": ("hypervisor", "internal_run", "bootstrap", "status", "control", "runtime"),
}

POSITIVE_KEYWORDS = (
    "active",
    "approved",
    "completed",
    "available",
    "provenance",
    "context",
    "governance",
    "constitution",
)
NEGATIVE_KEYWORDS = (
    "rejected",
    "superseded",
    "failed",
    "cancelled",
    "interrupted",
    "denied",
    "error",
    "conflict",
)
NEUTRAL_KEYWORDS = ("queued", "pending", "preview", "sample", "staging", "idle")
SCAR_KEYWORDS = ("correct", "supersed", "duplicate", "interrupt", "rejected", "error")


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
            row_axes=self._row_axes(),
            column_axes=self._column_axes(),
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
        notes, warnings = self._projection_notes(source_totals)
        notes = [*notes, "Square detail lists source slices that contributed pressure to this board position."]
        return HybridBoardSquareDetailRecord(
            projection_version=self.PROJECTION_VERSION,
            read_only=True,
            requested_room_id=requested_room_id,
            resolved_room_ids=resolved_room_ids,
            row_axes=self._row_axes(),
            column_axes=self._column_axes(),
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
        text = self._normalize_text(tokens)
        row = self._pick_axis(definitions=BOARD_ROWS, keyword_map=ROW_KEYWORDS, text=text, seed=f"row:{source_kind}:{source_id}")
        column = self._pick_axis(
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

        if self._contains_any(text, NEGATIVE_KEYWORDS):
            infernal += base_weight * 1.1
            scar += base_weight * 0.55
        if normalized_status in {"rejected", "superseded"}:
            infernal += base_weight * 1.4
            scar += base_weight * 0.9
        if normalized_status in {"active", "completed"}:
            celestial += base_weight * 0.95
        if self._contains_any(text, POSITIVE_KEYWORDS):
            celestial += base_weight * 0.85
        if self._contains_any(text, NEUTRAL_KEYWORDS):
            neutral += base_weight * 0.65
        if self._contains_any(text, SCAR_KEYWORDS):
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

        normalized_markers = [normalized for marker in markers if (normalized := self._normalize_marker(marker))]
        for marker in normalized_markers:
            acc.markers[marker] += 1
        acc.sources.append(
            _SquareSourceRef(
                source_kind=source_kind,
                source_id=source_id,
                room_id=room_id,
                title=title,
                summary=self._truncate(summary, 220),
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

    def _row_axes(self) -> list[HybridBoardAxisRecord]:
        return [
            HybridBoardAxisRecord(id=row.id, index=index, label=row.label, description=row.description)
            for index, row in enumerate(BOARD_ROWS)
        ]

    def _column_axes(self) -> list[HybridBoardAxisRecord]:
        return [
            HybridBoardAxisRecord(id=column.id, index=index, label=column.label, description=column.description)
            for index, column in enumerate(BOARD_COLUMNS)
        ]

    def _pick_axis(
        self,
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

    @staticmethod
    def _normalize_text(values: list[object]) -> str:
        return " ".join(str(value).strip().lower() for value in values if value is not None and str(value).strip())

    @staticmethod
    def _normalize_marker(value: object) -> str | None:
        text = str(value).strip().lower() if value is not None else ""
        return text or None

    @staticmethod
    def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
        return any(keyword in text for keyword in keywords)

    @staticmethod
    def _truncate(value: str, limit: int) -> str:
        text = value.strip()
        if len(text) <= limit:
            return text
        return f"{text[: limit - 1].rstrip()}…"


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
                anchor_type = self._anchor_type_for_asset_kind(str(row.get("asset_kind") or "generic"))
                cluster_id = f"{room_id}:{row['dataset_id']}:{anchor_prefix}:{anchor_type}"
                node_rows.append(
                    {
                        "node_id": f"asset:{row['id']}",
                        "cluster_id": cluster_id,
                        "room_id": room_id,
                        "dataset_id": int(row["dataset_id"]),
                        "dataset_label": str(row.get("dataset_label") or dataset.get("label") or f"dataset {row['dataset_id']}"),
                        "asset_id": int(row["id"]),
                        "asset_kind": str(row.get("asset_kind") or "generic"),
                        "anchor_type": anchor_type,
                        "label": self._asset_label(row),
                        "relative_path": relative_path,
                        "file_name": str(row.get("file_name") or ""),
                        "size_bytes": size_bytes,
                        "indexed_at": str(row.get("indexed_at") or ""),
                        "fs_modified_at": str(row.get("fs_modified_at") or ""),
                        "anchor_prefix": anchor_prefix,
                    }
                )

        clusters: dict[str, dict[str, object]] = defaultdict(
            lambda: {
                "room_id": "",
                "dataset_id": 0,
                "dataset_label": "",
                "anchor_prefix": "",
                "label": "",
                "node_count": 0,
                "asset_kind_counter": Counter(),
                "recent_indexed_at": None,
            }
        )

        nodes: list[WorldMemoryNodeRecord] = []
        for index, row in enumerate(sorted(node_rows, key=lambda item: (str(item["indexed_at"]), str(item["node_id"])), reverse=True)):
            cluster = clusters[str(row["cluster_id"])]
            cluster["room_id"] = row["room_id"]
            cluster["dataset_id"] = row["dataset_id"]
            cluster["dataset_label"] = row["dataset_label"]
            cluster["anchor_prefix"] = row["anchor_prefix"]
            cluster["label"] = self._cluster_label(str(row["dataset_label"]), str(row["anchor_prefix"]), str(row["anchor_type"]))
            cluster["node_count"] += 1
            cluster["asset_kind_counter"][str(row["asset_kind"])] += 1
            current_recent = cluster["recent_indexed_at"]
            if current_recent is None or str(row["indexed_at"]) > str(current_recent):
                cluster["recent_indexed_at"] = row["indexed_at"]

            intensity = self._node_intensity(size_bytes=int(row["size_bytes"]), max_size=max_size, index=index)
            nodes.append(
                WorldMemoryNodeRecord(
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
                )
            )

        cluster_records = [
            WorldMemoryClusterRecord(
                cluster_id=cluster_id,
                room_id=str(payload["room_id"]),
                dataset_id=int(payload["dataset_id"]),
                dataset_label=str(payload["dataset_label"]),
                anchor_prefix=str(payload["anchor_prefix"]),
                label=str(payload["label"]),
                node_count=int(payload["node_count"]),
                dominant_asset_kind=payload["asset_kind_counter"].most_common(1)[0][0]
                if payload["asset_kind_counter"]
                else "generic",
                recent_indexed_at=str(payload["recent_indexed_at"]) if payload["recent_indexed_at"] else None,
            )
            for cluster_id, payload in sorted(
                clusters.items(),
                key=lambda item: (-(int(item[1]["node_count"])), str(item[0])),
            )
        ]

        notes = [
            "World Memory v1 is a governed asset-anchor shell, not a 3D reconstruction engine yet.",
            "Nodes are derived from indexed local assets and grouped into deterministic clusters by room, dataset, and path prefix.",
            "This shell exists to give later place-memory, depth, and reconstruction layers a governed starting surface.",
        ]
        warnings: list[str] = []
        if not nodes:
            warnings.append("No indexed assets were available to build the world-memory shell yet.")

        return WorldMemoryRecord(
            projection_version=self.PROJECTION_VERSION,
            read_only=True,
            requested_room_id=requested_room_id,
            resolved_room_ids=resolved_room_ids,
            node_count=len(nodes),
            cluster_count=len(cluster_records),
            anchor_types=sorted({node.anchor_type for node in nodes}),
            clusters=cluster_records,
            nodes=nodes[:72],
            notes=notes,
            warnings=warnings,
        )

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
