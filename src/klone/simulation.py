from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import hashlib

from .memory import MemoryService
from .repository import KloneRepository
from .schemas import (
    HybridBoardAxisRecord,
    HybridBoardSourceTotalsRecord,
    HybridBoardSquareRecord,
    HybridMemoryBoardRecord,
)


@dataclass(frozen=True)
class _AxisDefinition:
    id: str
    label: str
    description: str


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
                    markers=[
                        row.get("event_type"),
                        row.get("target_type"),
                        row.get("classification_level"),
                    ],
                    touched_at=row.get("created_at"),
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
                )

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

        notes = [
            "This board is a governed read-only projection over audit, memory events, and memory episodes.",
            "Mythic labels are runtime surfaces only; the existing audit and memory records remain source truth.",
            "Square pressure is deterministic and derived from typed system evidence, not from hidden model state.",
        ]
        warnings: list[str] = []
        if sum(source_totals.values()) == 0:
            warnings.append("No audit or memory sources were available for this board projection yet.")

        return HybridMemoryBoardRecord(
            projection_version=self.PROJECTION_VERSION,
            read_only=True,
            requested_room_id=requested_room_id,
            resolved_room_ids=resolved_room_ids,
            square_count=len(squares),
            source_totals=HybridBoardSourceTotalsRecord(**source_totals),
            row_axes=[
                HybridBoardAxisRecord(id=row.id, index=index, label=row.label, description=row.description)
                for index, row in enumerate(BOARD_ROWS)
            ],
            column_axes=[
                HybridBoardAxisRecord(
                    id=column.id,
                    index=index,
                    label=column.label,
                    description=column.description,
                )
                for index, column in enumerate(BOARD_COLUMNS)
            ],
            squares=squares,
            notes=notes,
            warnings=warnings,
        )

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
    ) -> None:
        text = self._normalize_text(tokens)
        row = self._pick_axis(
            definitions=BOARD_ROWS,
            keyword_map=ROW_KEYWORDS,
            text=text,
            seed=f"row:{source_kind}:{source_id}",
        )
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

        for marker in markers:
            normalized_marker = self._normalize_marker(marker)
            if normalized_marker:
                acc.markers[normalized_marker] += 1

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
