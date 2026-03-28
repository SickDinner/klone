from __future__ import annotations

from collections.abc import Mapping
import json
import sqlite3
from typing import Any

from .audit import AuditService
from .guards import access_guard, classification_guard
from .repository import KloneRepository, utc_now_iso
from .rooms import room_registry
from .schemas import (
    MemoryCorrectionResult,
    MemoryContextPackageRecord,
    MemoryReplayRequestInternal,
    MemoryReplayResult,
    MemorySeedResult,
)


ELIGIBLE_AUDIT_EVENT_TYPES = {
    "dataset_registered",
    "dataset_updated",
    "ingest_requested",
    "ingest_started",
    "ingest_completed",
    "ingest_blocked",
}

SEED_VERSION = "phase_2b_2"
SYSTEM_ACTOR_CANONICAL_KEY = "system_actor:system"


def _decode_metadata(raw_metadata: str | None) -> dict[str, Any] | None:
    if not raw_metadata:
        return None
    return json.loads(raw_metadata)


def _decode_row_metadata(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(payload)
    metadata_json = data.pop("metadata_json", None)
    if metadata_json:
        data["metadata"] = json.loads(metadata_json)
    return data


def _stable_fact_string(fields: list[tuple[str, Any]]) -> str:
    parts: list[str] = []
    for key, value in fields:
        if value is None:
            continue
        if isinstance(value, (dict, list)):
            rendered = json.dumps(value, sort_keys=True, separators=(",", ":"))
        else:
            rendered = str(value)
        parts.append(f"{key}={rendered}")
    return "|".join(parts)


def _metadata_value(metadata: Mapping[str, Any] | None, key: str) -> Any:
    if metadata is None:
        return None
    return metadata.get(key)


def _normalize_canonical_key(prefix: str, value: str | int) -> str:
    return f"{prefix}:{str(value).strip().lower()}"


def system_ingest_episode_id(*, room_id: str, ingest_run_id: int) -> str:
    return f"episode:system_ingest_run:{room_id}:{ingest_run_id}"


class MemoryService:
    def __init__(self, repository: KloneRepository) -> None:
        self.repository = repository
        self.audit_service = AuditService(repository)

    def seed_from_audit_events(
        self,
        *,
        room_id: str,
        audit_event_ids: list[int],
        ingest_run_id: int | None = None,
        seed_version: str = SEED_VERSION,
        conn: sqlite3.Connection | None = None,
    ) -> MemorySeedResult:
        room = self._require_room(room_id)
        result = MemorySeedResult(
            room_id=room_id,
            ingest_run_id=ingest_run_id,
            seed_version=seed_version,
        )

        self._ensure_write_access(room_id=room_id, actor_role="owner", result=result, conn=conn, mode="seed")
        self._log_batch_started(
            mode="seed",
            room_id=room_id,
            ingest_run_id=ingest_run_id,
            seed_version=seed_version,
            room_classification=room.classification,
            metadata={"audit_event_ids": audit_event_ids},
            conn=conn,
        )

        try:
            source_events = self.repository.list_audit_events_by_ids(
                audit_event_ids,
                room_id=room_id,
                conn=conn,
            )
            eligible_events = [
                event for event in source_events if event["event_type"] in ELIGIBLE_AUDIT_EVENT_TYPES
            ]
            self._materialize_memory(
                room_id=room_id,
                source_events=eligible_events,
                explicit_ingest_run_id=ingest_run_id,
                seed_version=seed_version,
                result=result,
                conn=conn,
            )
        except PermissionError as error:
            self._log_batch_blocked(
                mode="seed",
                room_id=room_id,
                ingest_run_id=ingest_run_id,
                room_classification=room.classification,
                reason=str(error),
                result=result,
                conn=conn,
            )
            raise

        self._log_batch_completed(
            mode="seed",
            room_id=room_id,
            ingest_run_id=ingest_run_id,
            room_classification=room.classification,
            result=result,
            conn=conn,
        )
        return result

    def replay_memory_generation(
        self,
        *,
        room_id: str,
        ingest_run_id: int | None = None,
        actor_role: str = "owner",
        seed_version: str = SEED_VERSION,
        conn: sqlite3.Connection | None = None,
    ) -> MemoryReplayResult:
        request = MemoryReplayRequestInternal(
            room_id=room_id,
            ingest_run_id=ingest_run_id,
            actor_role=actor_role,
            seed_version=seed_version,
        )
        room = self._require_room(request.room_id)
        result = MemoryReplayResult(
            room_id=request.room_id,
            ingest_run_id=request.ingest_run_id,
            seed_version=request.seed_version,
        )

        self._ensure_write_access(
            room_id=request.room_id,
            actor_role=request.actor_role,
            result=result,
            conn=conn,
            mode="replay",
        )
        self._log_batch_started(
            mode="replay",
            room_id=request.room_id,
            ingest_run_id=request.ingest_run_id,
            seed_version=request.seed_version,
            room_classification=room.classification,
            metadata={"actor_role": request.actor_role},
            conn=conn,
        )

        try:
            source_events = self._source_events_for_replay(
                room_id=request.room_id,
                ingest_run_id=request.ingest_run_id,
                conn=conn,
            )
            self._materialize_memory(
                room_id=request.room_id,
                source_events=source_events,
                explicit_ingest_run_id=request.ingest_run_id,
                seed_version=request.seed_version,
                result=result,
                conn=conn,
            )
        except PermissionError as error:
            self._log_batch_blocked(
                mode="replay",
                room_id=request.room_id,
                ingest_run_id=request.ingest_run_id,
                room_classification=room.classification,
                reason=str(error),
                result=result,
                conn=conn,
            )
            raise

        self._log_batch_completed(
            mode="replay",
            room_id=request.room_id,
            ingest_run_id=request.ingest_run_id,
            room_classification=room.classification,
            result=result,
            conn=conn,
        )
        return result

    def reject_event(
        self,
        *,
        room_id: str,
        event_id: int,
        reason: str,
        actor_role: str = "owner",
        conn: sqlite3.Connection | None = None,
    ) -> MemoryCorrectionResult:
        room = self._require_room(room_id)
        normalized_reason = self._normalize_correction_reason(reason)
        self._log_correction_started(
            room_id=room_id,
            memory_kind="event",
            memory_id=str(event_id),
            operation="reject_event",
            reason=normalized_reason,
            actor_role=actor_role,
            classification_level=room.classification,
            conn=conn,
        )

        try:
            self._ensure_correction_access(room_id=room_id, actor_role=actor_role)
            event_row = self.repository.get_memory_event_for_correction(
                event_id,
                room_id=room_id,
                conn=conn,
            )
            if event_row is None:
                raise ValueError(f"Memory event {event_id} was not found in room {room_id}.")
            self._ensure_room_classification(
                room_id=room_id,
                classification_level=event_row["classification_level"],
            )
            correction = self._resolve_event_rejection(
                event_row=event_row,
                reason=normalized_reason,
                actor_role=actor_role,
                conn=conn,
            )
        except (PermissionError, ValueError) as error:
            self._log_correction_blocked(
                room_id=room_id,
                memory_kind="event",
                memory_id=str(event_id),
                operation="reject_event",
                reason=normalized_reason,
                actor_role=actor_role,
                classification_level=room.classification,
                previous_status=None,
                resulting_status=None,
                superseded_by_id=None,
                block_reason=str(error),
                conn=conn,
            )
            raise

        self._log_correction_completed(
            result=correction,
            reason=normalized_reason,
            actor_role=actor_role,
            classification_level=room.classification,
            conn=conn,
        )
        return correction

    def reject_episode(
        self,
        *,
        room_id: str,
        episode_id: str,
        reason: str,
        actor_role: str = "owner",
        conn: sqlite3.Connection | None = None,
    ) -> MemoryCorrectionResult:
        room = self._require_room(room_id)
        normalized_reason = self._normalize_correction_reason(reason)
        self._log_correction_started(
            room_id=room_id,
            memory_kind="episode",
            memory_id=episode_id,
            operation="reject_episode",
            reason=normalized_reason,
            actor_role=actor_role,
            classification_level=room.classification,
            conn=conn,
        )

        try:
            self._ensure_correction_access(room_id=room_id, actor_role=actor_role)
            episode_row = self.repository.get_memory_episode_for_correction(
                episode_id,
                room_id=room_id,
                conn=conn,
            )
            if episode_row is None:
                raise ValueError(f"Memory episode {episode_id} was not found in room {room_id}.")
            self._ensure_room_classification(
                room_id=room_id,
                classification_level=episode_row["classification_level"],
            )
            correction = self._resolve_episode_rejection(
                episode_row=episode_row,
                reason=normalized_reason,
                actor_role=actor_role,
                conn=conn,
            )
        except (PermissionError, ValueError) as error:
            self._log_correction_blocked(
                room_id=room_id,
                memory_kind="episode",
                memory_id=episode_id,
                operation="reject_episode",
                reason=normalized_reason,
                actor_role=actor_role,
                classification_level=room.classification,
                previous_status=None,
                resulting_status=None,
                superseded_by_id=None,
                block_reason=str(error),
                conn=conn,
            )
            raise

        self._log_correction_completed(
            result=correction,
            reason=normalized_reason,
            actor_role=actor_role,
            classification_level=room.classification,
            conn=conn,
        )
        return correction

    def supersede_event(
        self,
        *,
        room_id: str,
        event_id: int,
        superseded_by_event_id: int,
        reason: str,
        actor_role: str = "owner",
        conn: sqlite3.Connection | None = None,
    ) -> MemoryCorrectionResult:
        room = self._require_room(room_id)
        normalized_reason = self._normalize_correction_reason(reason)
        self._log_correction_started(
            room_id=room_id,
            memory_kind="event",
            memory_id=str(event_id),
            operation="supersede_event",
            reason=normalized_reason,
            actor_role=actor_role,
            classification_level=room.classification,
            superseded_by_id=superseded_by_event_id,
            conn=conn,
        )

        try:
            self._ensure_correction_access(room_id=room_id, actor_role=actor_role)
            source_event = self.repository.get_memory_event_for_correction(
                event_id,
                room_id=room_id,
                conn=conn,
            )
            if source_event is None:
                raise ValueError(f"Memory event {event_id} was not found in room {room_id}.")
            replacement_event = self.repository.validate_same_room_event_reference(
                room_id=room_id,
                event_id=event_id,
                reference_event_id=superseded_by_event_id,
                conn=conn,
            )
            if replacement_event is None:
                raise ValueError(
                    f"Replacement memory event {superseded_by_event_id} was not found in room {room_id}."
                )
            if event_id == superseded_by_event_id:
                raise ValueError("A memory event cannot supersede itself.")
            self._ensure_room_classification(
                room_id=room_id,
                classification_level=source_event["classification_level"],
            )
            self._ensure_room_classification(
                room_id=room_id,
                classification_level=replacement_event["classification_level"],
            )
            correction = self._resolve_event_supersession(
                source_event=source_event,
                replacement_event=replacement_event,
                reason=normalized_reason,
                actor_role=actor_role,
                conn=conn,
            )
        except (PermissionError, ValueError) as error:
            self._log_correction_blocked(
                room_id=room_id,
                memory_kind="event",
                memory_id=str(event_id),
                operation="supersede_event",
                reason=normalized_reason,
                actor_role=actor_role,
                classification_level=room.classification,
                previous_status=None,
                resulting_status=None,
                superseded_by_id=superseded_by_event_id,
                block_reason=str(error),
                conn=conn,
            )
            raise

        self._log_correction_completed(
            result=correction,
            reason=normalized_reason,
            actor_role=actor_role,
            classification_level=room.classification,
            conn=conn,
        )
        return correction

    def _attach_provenance_summary(
        self,
        *,
        room_id: str,
        owner_type: str,
        owner_id: str,
        payload: dict[str, Any],
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any]:
        hydrated = dict(payload)
        provenance = self.repository.list_memory_provenance(
            room_id=room_id,
            owner_type=owner_type,
            owner_id=owner_id,
            conn=conn,
        )
        hydrated["provenance_summary"] = self._build_provenance_summary(provenance)
        return hydrated

    def query_events(
        self,
        *,
        room_id: str,
        limit: int,
        offset: int,
        status: str | None = None,
        event_type: str | None = None,
        ingest_run_id: int | None = None,
        include_corrected: bool = True,
    ) -> list[dict[str, Any]]:
        self._require_room(room_id)
        rows = self.repository.list_memory_events(
            room_id=room_id,
            limit=limit,
            offset=offset,
            status=status,
            event_type=event_type,
            ingest_run_id=ingest_run_id,
            include_corrected=include_corrected,
        )
        return [
            self._attach_provenance_summary(
                room_id=room_id,
                owner_type="event",
                owner_id=str(row["id"]),
                payload=_decode_row_metadata(row),
            )
            for row in rows
        ]

    def query_episodes(
        self,
        *,
        room_id: str,
        limit: int,
        offset: int,
        status: str | None = None,
        episode_type: str | None = None,
        ingest_run_id: int | None = None,
        include_corrected: bool = True,
    ) -> list[dict[str, Any]]:
        self._require_room(room_id)
        rows = self.repository.list_memory_episodes(
            room_id=room_id,
            limit=limit,
            offset=offset,
            status=status,
            episode_type=episode_type,
            ingest_run_id=ingest_run_id,
            include_corrected=include_corrected,
        )
        return [
            self._attach_provenance_summary(
                room_id=room_id,
                owner_type="episode",
                owner_id=row["id"],
                payload=_decode_row_metadata(row),
            )
            for row in rows
        ]

    def assemble_context_package(
        self,
        *,
        room_id: str,
        event_id: int | None = None,
        episode_id: str | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> MemoryContextPackageRecord:
        self._require_room(room_id)
        if (event_id is None) == (episode_id is None):
            raise ValueError("Exactly one of event_id or episode_id is required.")
        if event_id is not None:
            return self._assemble_event_context_package(
                room_id=room_id,
                event_id=event_id,
                conn=conn,
            )
        return self._assemble_episode_context_package(
            room_id=room_id,
            episode_id=episode_id,
            conn=conn,
        )

    def _assemble_event_context_package(
        self,
        *,
        room_id: str,
        event_id: int,
        conn: sqlite3.Connection | None = None,
    ) -> MemoryContextPackageRecord:
        event_detail = self.get_event_detail(room_id=room_id, event_id=event_id, conn=conn)
        if event_detail is None:
            raise ValueError(f"Memory event {event_id} was not found in room {room_id}.")

        included_episodes: list[dict[str, Any]] = []
        seen_episode_ids: set[str] = set()
        for membership in event_detail.get("episode_memberships", []):
            membership_episode_id = membership["episode"]["id"]
            if membership_episode_id in seen_episode_ids:
                continue
            episode_detail = self.get_episode_detail(
                room_id=room_id,
                episode_id=membership_episode_id,
                conn=conn,
            )
            if episode_detail is None:
                continue
            seen_episode_ids.add(membership_episode_id)
            included_episodes.append(episode_detail)

        included_events = [event_detail]
        return MemoryContextPackageRecord.model_validate(
            {
                "room_id": room_id,
                "query_scope": {
                    "scope_kind": "event_detail",
                    "primary_event_id": event_id,
                    "primary_episode_id": None,
                },
                "included_events": included_events,
                "included_episodes": included_episodes,
                "provenance_summary": self._build_context_provenance_summary(
                    event_payloads=included_events,
                    episode_payloads=included_episodes,
                ),
                "correction_summary": self._build_context_correction_summary(
                    event_payloads=included_events,
                    episode_payloads=included_episodes,
                ),
                "warnings": self._build_context_warnings(
                    scope_kind="event_detail",
                    included_events=included_events,
                    included_episodes=included_episodes,
                ),
                "limitations": self._context_limitations(),
                "assembly_reasoning": [
                    "Used the requested room-scoped event detail as the primary record.",
                    "Included episode details from stored event memberships in deterministic sequence order.",
                    "Preserved stored provenance, correction state, supersession visibility, and evidence text without inference.",
                ],
            }
        )

    def _assemble_episode_context_package(
        self,
        *,
        room_id: str,
        episode_id: str,
        conn: sqlite3.Connection | None = None,
    ) -> MemoryContextPackageRecord:
        episode_detail = self.get_episode_detail(room_id=room_id, episode_id=episode_id, conn=conn)
        if episode_detail is None:
            raise ValueError(f"Memory episode {episode_id} was not found in room {room_id}.")

        included_events: list[dict[str, Any]] = []
        seen_event_ids: set[int] = set()
        for linked_event in episode_detail.get("linked_events", []):
            linked_event_id = int(linked_event["event"]["id"])
            if linked_event_id in seen_event_ids:
                continue
            event_detail = self.get_event_detail(
                room_id=room_id,
                event_id=linked_event_id,
                conn=conn,
            )
            if event_detail is None:
                continue
            seen_event_ids.add(linked_event_id)
            included_events.append(event_detail)

        included_episodes = [episode_detail]
        return MemoryContextPackageRecord.model_validate(
            {
                "room_id": room_id,
                "query_scope": {
                    "scope_kind": "episode_detail",
                    "primary_event_id": None,
                    "primary_episode_id": episode_id,
                },
                "included_events": included_events,
                "included_episodes": included_episodes,
                "provenance_summary": self._build_context_provenance_summary(
                    event_payloads=included_events,
                    episode_payloads=included_episodes,
                ),
                "correction_summary": self._build_context_correction_summary(
                    event_payloads=included_events,
                    episode_payloads=included_episodes,
                ),
                "warnings": self._build_context_warnings(
                    scope_kind="episode_detail",
                    included_events=included_events,
                    included_episodes=included_episodes,
                ),
                "limitations": self._context_limitations(),
                "assembly_reasoning": [
                    "Used the requested room-scoped episode detail as the primary record.",
                    "Included event details from stored episode memberships in deterministic sequence order.",
                    "Preserved stored provenance, correction state, supersession visibility, and evidence text without inference.",
                ],
            }
        )

    def _build_context_provenance_summary(
        self,
        *,
        event_payloads: list[dict[str, Any]],
        episode_payloads: list[dict[str, Any]],
    ) -> dict[str, Any]:
        unique_provenance: dict[int, dict[str, Any]] = {}
        for payload in [*event_payloads, *episode_payloads]:
            for provenance_row in payload.get("provenance", []):
                unique_provenance[int(provenance_row["id"])] = dict(provenance_row)

        ordered_rows = sorted(
            unique_provenance.values(),
            key=lambda row: (
                row["owner_type"],
                row["owner_id"],
                row["provenance_type"],
                row["source_table"],
                row["source_record_id"],
                row["basis_type"],
                row["id"],
            ),
        )
        return self._build_provenance_summary(ordered_rows)

    def _build_context_correction_summary(
        self,
        *,
        event_payloads: list[dict[str, Any]],
        episode_payloads: list[dict[str, Any]],
    ) -> dict[str, Any]:
        corrected_event_ids = sorted(
            event["id"] for event in event_payloads if event["status"] in {"rejected", "superseded"}
        )
        corrected_episode_ids = sorted(
            episode["id"] for episode in episode_payloads if episode["status"] != "active"
        )
        rejected_event_ids = sorted(
            event["id"] for event in event_payloads if event["status"] == "rejected"
        )
        rejected_episode_ids = sorted(
            episode["id"] for episode in episode_payloads if episode["status"] == "rejected"
        )
        superseded_event_ids = sorted(
            event["id"] for event in event_payloads if event["status"] == "superseded"
        )

        supersession_links: dict[str, dict[str, Any]] = {}
        for event in event_payloads:
            for relationship in event.get("supersession_relationships", []):
                supersession_links[relationship["id"]] = {
                    "id": relationship["id"],
                    "room_id": relationship["room_id"],
                    "old_event_id": relationship["old_event_id"],
                    "new_event_id": relationship["new_event_id"],
                    "reason": relationship.get("reason"),
                    "created_at": relationship["created_at"],
                    "created_by_role": relationship["created_by_role"],
                }

        return {
            "corrected_event_ids": corrected_event_ids,
            "corrected_episode_ids": corrected_episode_ids,
            "rejected_event_ids": rejected_event_ids,
            "rejected_episode_ids": rejected_episode_ids,
            "superseded_event_ids": superseded_event_ids,
            "supersession_links": sorted(
                supersession_links.values(),
                key=lambda item: (item["old_event_id"], item["new_event_id"], item["id"]),
            ),
        }

    def _build_context_warnings(
        self,
        *,
        scope_kind: str,
        included_events: list[dict[str, Any]],
        included_episodes: list[dict[str, Any]],
    ) -> list[str]:
        warnings: list[str] = []
        if scope_kind == "event_detail" and not included_episodes:
            warnings.append("no_linked_episodes_included")
        if scope_kind == "episode_detail" and not included_events:
            warnings.append("no_linked_events_included")
        return warnings

    def _context_limitations(self) -> list[str]:
        return [
            "Read-only package assembled from stored room-scoped memory only.",
            "No LLM calls, semantic ranking, embeddings, or inferred facts were used.",
            "Package includes only stored records reachable from the requested root record.",
            "evidence_text is preserved exactly from stored memory rows.",
        ]

    def list_event_episode_memberships(
        self,
        *,
        room_id: str,
        event_id: int,
        limit: int,
        offset: int,
        conn: sqlite3.Connection | None = None,
    ) -> list[dict[str, Any]]:
        membership_rows = self.repository.list_memory_event_episode_memberships(
            event_id,
            room_id=room_id,
            limit=limit,
            offset=offset,
            conn=conn,
        )
        memberships: list[dict[str, Any]] = []
        for row in membership_rows:
            episode_payload = {
                "id": row["episode_id"],
                "room_id": row["episode_room_id"],
                "classification_level": row["episode_classification_level"],
                "episode_type": row["episode_type"],
                "grouping_basis": row["grouping_basis"],
                "source_table": row["episode_source_table"],
                "source_record_id": row["episode_source_record_id"],
                "title": row["episode_title"],
                "summary": row["episode_summary"],
                "status": row["episode_status"],
                "correction_reason": row["episode_correction_reason"],
                "corrected_at": row["episode_corrected_at"],
                "corrected_by_role": row["episode_corrected_by_role"],
                "start_at": row["start_at"],
                "end_at": row["end_at"],
                "metadata_json": row["episode_metadata_json"],
                "created_at": row["episode_created_at"],
                "updated_at": row["episode_updated_at"],
            }
            memberships.append(
                {
                    "sequence_no": row["sequence_no"],
                    "inclusion_basis": row["inclusion_basis"],
                    "episode": _decode_row_metadata(episode_payload),
                }
            )
        return memberships

    def list_event_supersession_relationships(
        self,
        *,
        room_id: str,
        event_id: int,
        conn: sqlite3.Connection | None = None,
    ) -> list[dict[str, Any]]:
        return self.repository.list_memory_event_supersession_relationships(
            event_id,
            room_id=room_id,
            conn=conn,
        )

    def get_event_detail(
        self,
        *,
        room_id: str,
        event_id: int,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any] | None:
        event_row = self.repository.get_memory_event(event_id, room_id=room_id, conn=conn)
        if event_row is None:
            return None

        provenance = self.repository.list_memory_provenance(
            room_id=room_id,
            owner_type="event",
            owner_id=str(event_id),
            conn=conn,
        )
        linked_entities = [
            _decode_row_metadata(row)
            for row in self.repository.list_memory_event_entity_details(
                event_id,
                room_id=room_id,
                conn=conn,
            )
        ]
        episode_memberships = self.list_event_episode_memberships(
            room_id=room_id,
            event_id=event_id,
            limit=200,
            offset=0,
            conn=conn,
        )
        supersession_relationships = self.list_event_supersession_relationships(
            room_id=room_id,
            event_id=event_id,
            conn=conn,
        )
        payload = _decode_row_metadata(event_row)
        payload["corrected"] = payload.get("status") in {"rejected", "superseded"}
        payload["provenance"] = provenance
        payload["source_lineage"] = [
            row for row in provenance if row["provenance_type"] == "source_lineage"
        ]
        payload["seed_basis"] = [row for row in provenance if row["provenance_type"] == "seed_basis"]
        payload["provenance_summary"] = self._build_provenance_summary(provenance)
        payload["linked_entities"] = linked_entities
        payload["episode_memberships"] = episode_memberships
        payload["supersession_relationships"] = supersession_relationships
        return payload

    def get_episode_detail(
        self,
        *,
        room_id: str,
        episode_id: str,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any] | None:
        episode_row = self.repository.get_memory_episode(episode_id, room_id=room_id, conn=conn)
        if episode_row is None:
            return None

        provenance = self.repository.list_memory_provenance(
            room_id=room_id,
            owner_type="episode",
            owner_id=episode_id,
            conn=conn,
        )
        linked_events = self.list_episode_members(
            room_id=room_id,
            episode_id=episode_id,
            limit=500,
            offset=0,
            conn=conn,
        )
        payload = _decode_row_metadata(episode_row)
        payload["provenance"] = provenance
        payload["source_lineage"] = [
            row for row in provenance if row["provenance_type"] == "source_lineage"
        ]
        payload["seed_basis"] = [row for row in provenance if row["provenance_type"] == "seed_basis"]
        payload["membership_basis"] = [
            row for row in provenance if row["provenance_type"] == "membership_basis"
        ]
        payload["linked_events"] = linked_events
        payload["provenance_summary"] = self._build_provenance_summary(provenance)
        return payload

    def list_episode_members(
        self,
        *,
        room_id: str,
        episode_id: str,
        limit: int,
        offset: int,
        conn: sqlite3.Connection | None = None,
    ) -> list[dict[str, Any]]:
        member_rows = self.repository.list_memory_episode_member_details(
            episode_id,
            room_id=room_id,
            limit=limit,
            offset=offset,
            conn=conn,
        )
        members: list[dict[str, Any]] = []
        for row in member_rows:
            event_payload = {
                key: value
                for key, value in dict(row).items()
                if key not in {"sequence_no", "inclusion_basis"}
            }
            members.append(
                {
                    "sequence_no": row["sequence_no"],
                    "inclusion_basis": row["inclusion_basis"],
                    "event": _decode_row_metadata(event_payload),
                }
            )
        return members

    def _build_provenance_summary(self, provenance: list[dict[str, Any]]) -> dict[str, Any]:
        source_refs = sorted(
            {
                f"{row['source_table']}:{row['source_record_id']}"
                for row in provenance
            }
        )
        return {
            "total_count": len(provenance),
            "source_lineage_count": sum(
                1 for row in provenance if row["provenance_type"] == "source_lineage"
            ),
            "seed_basis_count": sum(
                1 for row in provenance if row["provenance_type"] == "seed_basis"
            ),
            "membership_basis_count": sum(
                1 for row in provenance if row["provenance_type"] == "membership_basis"
            ),
            "source_refs": source_refs,
        }

    def _resolve_event_rejection(
        self,
        *,
        event_row: Mapping[str, Any],
        reason: str,
        actor_role: str,
        conn: sqlite3.Connection | None = None,
    ) -> MemoryCorrectionResult:
        previous_status = event_row["status"]
        if previous_status == "rejected":
            if (
                event_row.get("correction_reason") == reason
                and event_row.get("superseded_by_id") is None
                and event_row.get("corrected_by_role") == actor_role
            ):
                return MemoryCorrectionResult(
                    room_id=event_row["room_id"],
                    memory_kind="event",
                    memory_id=str(event_row["id"]),
                    operation="reject_event",
                    previous_status="rejected",
                    resulting_status="rejected",
                    superseded_by_id=None,
                    corrected_at=event_row["corrected_at"],
                    corrected_by_role=event_row["corrected_by_role"],
                )
            raise ValueError("Memory event is already rejected with a different correction state.")
        if previous_status != "active":
            raise ValueError(f"Memory event cannot be rejected from status {previous_status}.")

        corrected_at = utc_now_iso()
        updated_row = self.repository.set_event_status(
            room_id=event_row["room_id"],
            event_id=event_row["id"],
            status="rejected",
            reason=reason,
            actor_role=actor_role,
            superseded_by_id=None,
            corrected_at=corrected_at,
            conn=conn,
        )
        if updated_row is None:
            raise ValueError(f"Memory event {event_row['id']} was not found in room {event_row['room_id']}.")
        return MemoryCorrectionResult(
            room_id=updated_row["room_id"],
            memory_kind="event",
            memory_id=str(updated_row["id"]),
            operation="reject_event",
            previous_status=previous_status,
            resulting_status=updated_row["status"],
            superseded_by_id=updated_row.get("superseded_by_id"),
            corrected_at=updated_row["corrected_at"],
            corrected_by_role=updated_row["corrected_by_role"],
        )

    def _resolve_episode_rejection(
        self,
        *,
        episode_row: Mapping[str, Any],
        reason: str,
        actor_role: str,
        conn: sqlite3.Connection | None = None,
    ) -> MemoryCorrectionResult:
        previous_status = episode_row["status"]
        if previous_status == "rejected":
            if (
                episode_row.get("correction_reason") == reason
                and episode_row.get("corrected_by_role") == actor_role
            ):
                return MemoryCorrectionResult(
                    room_id=episode_row["room_id"],
                    memory_kind="episode",
                    memory_id=str(episode_row["id"]),
                    operation="reject_episode",
                    previous_status="rejected",
                    resulting_status="rejected",
                    superseded_by_id=None,
                    corrected_at=episode_row["corrected_at"],
                    corrected_by_role=episode_row["corrected_by_role"],
                )
            raise ValueError("Memory episode is already rejected with a different correction state.")
        if previous_status != "active":
            raise ValueError(f"Memory episode cannot be rejected from status {previous_status}.")

        corrected_at = utc_now_iso()
        updated_row = self.repository.set_episode_status(
            room_id=episode_row["room_id"],
            episode_id=episode_row["id"],
            status="rejected",
            reason=reason,
            actor_role=actor_role,
            corrected_at=corrected_at,
            conn=conn,
        )
        if updated_row is None:
            raise ValueError(
                f"Memory episode {episode_row['id']} was not found in room {episode_row['room_id']}."
            )
        return MemoryCorrectionResult(
            room_id=updated_row["room_id"],
            memory_kind="episode",
            memory_id=str(updated_row["id"]),
            operation="reject_episode",
            previous_status=previous_status,
            resulting_status=updated_row["status"],
            superseded_by_id=None,
            corrected_at=updated_row["corrected_at"],
            corrected_by_role=updated_row["corrected_by_role"],
        )

    def _resolve_event_supersession(
        self,
        *,
        source_event: Mapping[str, Any],
        replacement_event: Mapping[str, Any],
        reason: str,
        actor_role: str,
        conn: sqlite3.Connection | None = None,
    ) -> MemoryCorrectionResult:
        if replacement_event["status"] != "active":
            raise ValueError("Replacement memory event must be active.")

        previous_status = source_event["status"]
        if previous_status == "superseded":
            if (
                source_event.get("superseded_by_id") == replacement_event["id"]
                and source_event.get("correction_reason") == reason
                and source_event.get("corrected_by_role") == actor_role
            ):
                self.repository.link_supersession(
                    source_event["room_id"],
                    source_event["id"],
                    replacement_event["id"],
                    reason,
                    actor_role,
                    conn=conn,
                )
                return MemoryCorrectionResult(
                    room_id=source_event["room_id"],
                    memory_kind="event",
                    memory_id=str(source_event["id"]),
                    operation="supersede_event",
                    previous_status="superseded",
                    resulting_status="superseded",
                    superseded_by_id=source_event["superseded_by_id"],
                    corrected_at=source_event["corrected_at"],
                    corrected_by_role=source_event["corrected_by_role"],
                )
            raise ValueError("Memory event is already superseded with a different correction state.")
        if previous_status != "active":
            raise ValueError(f"Memory event cannot be superseded from status {previous_status}.")

        corrected_at = utc_now_iso()
        self.repository.link_supersession(
            source_event["room_id"],
            source_event["id"],
            replacement_event["id"],
            reason,
            actor_role,
            conn=conn,
        )
        updated_row = self.repository.set_event_status(
            room_id=source_event["room_id"],
            event_id=source_event["id"],
            status="superseded",
            reason=reason,
            actor_role=actor_role,
            superseded_by_id=replacement_event["id"],
            corrected_at=corrected_at,
            conn=conn,
        )
        if updated_row is None:
            raise ValueError(
                f"Memory event {source_event['id']} was not found in room {source_event['room_id']}."
            )
        return MemoryCorrectionResult(
            room_id=updated_row["room_id"],
            memory_kind="event",
            memory_id=str(updated_row["id"]),
            operation="supersede_event",
            previous_status=previous_status,
            resulting_status=updated_row["status"],
            superseded_by_id=updated_row["superseded_by_id"],
            corrected_at=updated_row["corrected_at"],
            corrected_by_role=updated_row["corrected_by_role"],
        )

    def _materialize_memory(
        self,
        *,
        room_id: str,
        source_events: list[dict[str, Any]],
        explicit_ingest_run_id: int | None,
        seed_version: str,
        result: MemorySeedResult,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        memory_events: list[tuple[dict[str, Any], dict[str, Any]]] = []

        for source_event in source_events:
            event_row = self._seed_event_from_audit_row(source_event, conn=conn)
            if event_row is None:
                result.events_skipped += 1
                continue
            created = event_row.pop("_created")
            if created:
                result.events_written += 1
            else:
                result.events_upserted += 1
            memory_events.append((event_row, source_event))
            self._upsert_event_provenance(
                event_row=event_row,
                source_event=source_event,
                seed_version=seed_version,
                result=result,
                conn=conn,
            )

        for event_row, _ in memory_events:
            for entity_payload, link_payload in self._build_event_entity_payloads(
                event_row,
                conn=conn,
            ):
                self._ensure_room_classification(
                    room_id=entity_payload["room_id"],
                    classification_level=entity_payload["classification_level"],
                )
                entity_row, entity_created = self.repository.upsert_memory_entity(
                    entity_payload,
                    conn=conn,
                )
                if entity_created:
                    result.entities_written += 1
                else:
                    result.entities_upserted += 1

                self._ensure_room_classification(
                    room_id=event_row["room_id"],
                    classification_level=event_row["classification_level"],
                )
                _, link_created = self.repository.upsert_memory_event_entity_link(
                    {
                        **link_payload,
                        "event_id": event_row["id"],
                        "entity_id": entity_row["id"],
                    },
                    conn=conn,
                )
                if link_created:
                    result.event_entity_links_written += 1
                else:
                    result.event_entity_links_upserted += 1

        ingest_run_ids = self._episode_ingest_run_ids(
            explicit_ingest_run_id=explicit_ingest_run_id,
            memory_events=[event_row for event_row, _ in memory_events],
        )
        for ingest_run_id in ingest_run_ids:
            episode_row = self._seed_ingest_run_episode(
                room_id=room_id,
                ingest_run_id=ingest_run_id,
                conn=conn,
            )
            if episode_row is None:
                result.episodes_skipped += 1
                continue
            episode_created = episode_row.pop("_created")
            if episode_created:
                result.episodes_written += 1
            else:
                result.episodes_upserted += 1

            linked_events = self.repository.list_memory_events_for_ingest_run(
                room_id=room_id,
                ingest_run_id=ingest_run_id,
                conn=conn,
            )
            self._upsert_episode_provenance(
                episode_row=episode_row,
                linked_events=linked_events,
                seed_version=seed_version,
                result=result,
                conn=conn,
            )
            for sequence_no, event_row in enumerate(linked_events, start=1):
                self._ensure_room_classification(
                    room_id=event_row["room_id"],
                    classification_level=event_row["classification_level"],
                )
                _, link_created = self.repository.upsert_memory_episode_event_link(
                    {
                        "episode_id": episode_row["id"],
                        "event_id": event_row["id"],
                        "sequence_no": sequence_no,
                        "inclusion_basis": "ingest_run_id_exact_match",
                    },
                    conn=conn,
                )
                if link_created:
                    result.episode_event_links_written += 1
                else:
                    result.episode_event_links_upserted += 1

    def _source_events_for_replay(
        self,
        *,
        room_id: str,
        ingest_run_id: int | None,
        conn: sqlite3.Connection | None = None,
    ) -> list[dict[str, Any]]:
        source_events = self.repository.list_audit_events_for_room(room_id=room_id, conn=conn)
        eligible = [event for event in source_events if event["event_type"] in ELIGIBLE_AUDIT_EVENT_TYPES]
        if ingest_run_id is None:
            return eligible
        scoped_events: list[dict[str, Any]] = []
        for source_event in eligible:
            metadata = _decode_metadata(source_event.get("metadata_json"))
            if self._extract_exact_int(metadata, "ingest_run_id") == ingest_run_id:
                scoped_events.append(source_event)
        return scoped_events

    def _episode_ingest_run_ids(
        self,
        *,
        explicit_ingest_run_id: int | None,
        memory_events: list[dict[str, Any]],
    ) -> list[int]:
        if explicit_ingest_run_id is not None:
            return [explicit_ingest_run_id]
        run_ids = {
            ingest_run_id
            for event_row in memory_events
            if (ingest_run_id := event_row.get("ingest_run_id")) is not None
        }
        return sorted(run_ids)

    def _seed_event_from_audit_row(
        self,
        source_event: Mapping[str, Any],
        *,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any] | None:
        room_id = source_event.get("room_id")
        classification_level = source_event.get("classification_level")
        source_record_id = source_event.get("id")
        if room_id is None or classification_level is None or source_record_id is None:
            return None

        self._ensure_room_classification(
            room_id=room_id,
            classification_level=classification_level,
        )
        metadata = _decode_metadata(source_event.get("metadata_json"))
        evidence_text = self._build_evidence_text(source_event, metadata)
        if evidence_text is None:
            return None

        event_payload = {
            "room_id": room_id,
            "classification_level": classification_level,
            "event_type": source_event["event_type"],
            "source_table": "audit_events",
            "source_record_id": str(source_record_id),
            "dataset_id": self._extract_exact_int(metadata, "dataset_id"),
            "asset_id": None,
            "ingest_run_id": self._extract_exact_int(metadata, "ingest_run_id"),
            "occurred_at": source_event["created_at"],
            "recorded_at": source_event["created_at"],
            "title": source_event["event_type"],
            "evidence_text": evidence_text,
            "metadata": {
                "source_actor": source_event["actor"],
                "source_target_type": source_event["target_type"],
                "source_target_id": source_event["target_id"],
                "source_created_at": source_event["created_at"],
                "source_metadata": metadata,
            },
        }
        row, created = self.repository.upsert_memory_event(event_payload, conn=conn)
        row["_created"] = created
        return row

    def _build_event_entity_payloads(
        self,
        event_row: Mapping[str, Any],
        *,
        conn: sqlite3.Connection | None = None,
    ) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        room = room_registry.get_room(event_row["room_id"])
        if room is None:
            return []

        payloads: list[tuple[dict[str, Any], dict[str, Any]]] = []
        timestamp = event_row["occurred_at"]
        common = {
            "room_id": event_row["room_id"],
            "classification_level": event_row["classification_level"],
            "seed_source_event_id": event_row["id"],
            "first_seen_at": timestamp,
            "last_seen_at": timestamp,
        }

        payloads.append(
            (
                {
                    **common,
                    "entity_type": "room",
                    "canonical_name": room.label,
                    "canonical_key": _normalize_canonical_key("room", room.id),
                    "metadata": {"room_id": room.id},
                },
                {
                    "role": "context_room",
                    "source_basis": "memory_event.room_id",
                },
            )
        )

        payloads.append(
            (
                {
                    **common,
                    "entity_type": "system_actor",
                    "canonical_name": "system",
                    "canonical_key": SYSTEM_ACTOR_CANONICAL_KEY,
                    "metadata": {"actor": "system"},
                },
                {
                    "role": "system_actor",
                    "source_basis": "deterministic_system_actor",
                },
            )
        )

        dataset_id = event_row.get("dataset_id")
        if dataset_id is not None:
            dataset = self.repository.get_dataset(
                dataset_id,
                room_id=event_row["room_id"],
                conn=conn,
            )
            if dataset is not None:
                payloads.append(
                    (
                        {
                            **common,
                            "entity_type": "dataset",
                            "canonical_name": dataset["label"],
                            "canonical_key": _normalize_canonical_key("dataset", dataset_id),
                            "metadata": {"dataset_id": dataset_id},
                        },
                        {
                            "role": "subject_dataset",
                            "source_basis": "audit_metadata.dataset_id",
                        },
                    )
                )

        return payloads

    def _seed_ingest_run_episode(
        self,
        *,
        room_id: str,
        ingest_run_id: int,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any] | None:
        ingest_run = self.repository.get_ingest_run(
            ingest_run_id,
            room_id=room_id,
            conn=conn,
        )
        if ingest_run is None:
            return None

        room = self._require_room(room_id)
        self._ensure_room_classification(
            room_id=room_id,
            classification_level=room.classification,
        )

        episode_payload = {
            "id": system_ingest_episode_id(room_id=room_id, ingest_run_id=ingest_run_id),
            "room_id": room_id,
            "classification_level": room.classification,
            "episode_type": "system_ingest_run",
            "grouping_basis": str(ingest_run_id),
            "source_table": "ingest_runs",
            "source_record_id": str(ingest_run["id"]),
            "title": f"system_ingest_run:{ingest_run_id}",
            "summary": _stable_fact_string(
                [
                    ("episode_type", "system_ingest_run"),
                    ("room_id", room_id),
                    ("ingest_run_id", ingest_run["id"]),
                    ("dataset_id", ingest_run["dataset_id"]),
                    ("status", ingest_run["status"]),
                    ("trigger_source", ingest_run["trigger_source"]),
                    ("started_at", ingest_run["started_at"]),
                    ("completed_at", ingest_run["completed_at"]),
                    ("files_discovered", ingest_run["files_discovered"]),
                    ("assets_indexed", ingest_run["assets_indexed"]),
                    ("new_assets", ingest_run["new_assets"]),
                    ("updated_assets", ingest_run["updated_assets"]),
                    ("unchanged_assets", ingest_run["unchanged_assets"]),
                    ("duplicates_detected", ingest_run["duplicates_detected"]),
                    ("errors_detected", ingest_run["errors_detected"]),
                ]
            ),
            "start_at": ingest_run["started_at"],
            "end_at": ingest_run["completed_at"] or ingest_run["started_at"],
            "metadata": {
                "dataset_id": ingest_run["dataset_id"],
                "status": ingest_run["status"],
                "trigger_source": ingest_run["trigger_source"],
            },
        }
        row, created = self.repository.upsert_memory_episode(episode_payload, conn=conn)
        row["_created"] = created
        return row

    def _upsert_event_provenance(
        self,
        *,
        event_row: Mapping[str, Any],
        source_event: Mapping[str, Any],
        seed_version: str,
        result: MemorySeedResult,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        source_record_id = source_event.get("id")
        if source_record_id is None:
            result.provenance_skipped += 1
            return
        rows = [
            {
                "room_id": event_row["room_id"],
                "owner_type": "event",
                "owner_id": str(event_row["id"]),
                "provenance_type": "source_lineage",
                "source_table": "audit_events",
                "source_record_id": str(source_record_id),
                "source_field": None,
                "basis_type": "source_record",
                "basis_value": None,
            },
            {
                "room_id": event_row["room_id"],
                "owner_type": "event",
                "owner_id": str(event_row["id"]),
                "provenance_type": "seed_basis",
                "source_table": "audit_events",
                "source_record_id": str(source_record_id),
                "source_field": "event_type",
                "basis_type": "eligible_audit_event_type",
                "basis_value": str(source_event["event_type"]),
            },
            {
                "room_id": event_row["room_id"],
                "owner_type": "event",
                "owner_id": str(event_row["id"]),
                "provenance_type": "seed_basis",
                "source_table": "audit_events",
                "source_record_id": str(source_record_id),
                "source_field": "seed_version",
                "basis_type": "seed_version",
                "basis_value": seed_version,
            },
        ]
        self._upsert_provenance_rows(rows=rows, result=result, conn=conn)

    def _upsert_episode_provenance(
        self,
        *,
        episode_row: Mapping[str, Any],
        linked_events: list[dict[str, Any]],
        seed_version: str,
        result: MemorySeedResult,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        rows: list[dict[str, Any]] = [
            {
                "room_id": episode_row["room_id"],
                "owner_type": "episode",
                "owner_id": str(episode_row["id"]),
                "provenance_type": "source_lineage",
                "source_table": episode_row["source_table"],
                "source_record_id": episode_row["source_record_id"],
                "source_field": None,
                "basis_type": "source_record",
                "basis_value": None,
            },
            {
                "room_id": episode_row["room_id"],
                "owner_type": "episode",
                "owner_id": str(episode_row["id"]),
                "provenance_type": "seed_basis",
                "source_table": episode_row["source_table"],
                "source_record_id": episode_row["source_record_id"],
                "source_field": "grouping_basis",
                "basis_type": "grouping_basis",
                "basis_value": str(episode_row["grouping_basis"]),
            },
            {
                "room_id": episode_row["room_id"],
                "owner_type": "episode",
                "owner_id": str(episode_row["id"]),
                "provenance_type": "seed_basis",
                "source_table": episode_row["source_table"],
                "source_record_id": episode_row["source_record_id"],
                "source_field": "seed_version",
                "basis_type": "seed_version",
                "basis_value": seed_version,
            },
        ]

        for event_row in linked_events:
            rows.append(
                {
                    "room_id": episode_row["room_id"],
                    "owner_type": "episode",
                    "owner_id": str(episode_row["id"]),
                    "provenance_type": "membership_basis",
                    "source_table": "memory_events",
                    "source_record_id": str(event_row["id"]),
                    "source_field": "ingest_run_id",
                    "basis_type": "inclusion_basis",
                    "basis_value": "ingest_run_id_exact_match",
                }
            )

        self._upsert_provenance_rows(rows=rows, result=result, conn=conn)

    def _upsert_provenance_rows(
        self,
        *,
        rows: list[dict[str, Any]],
        result: MemorySeedResult,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        for row in rows:
            if not row.get("room_id") or not row.get("owner_id") or not row.get("source_record_id"):
                result.provenance_skipped += 1
                continue
            self._ensure_room_classification(
                room_id=row["room_id"],
                classification_level=self._require_room(row["room_id"]).classification,
            )
            _, created = self.repository.upsert_memory_provenance(row, conn=conn)
            if created:
                result.provenance_written += 1
            else:
                result.provenance_upserted += 1

    def _build_evidence_text(
        self,
        source_event: Mapping[str, Any],
        metadata: Mapping[str, Any] | None,
    ) -> str | None:
        common_fields = [
            ("event_type", source_event["event_type"]),
            ("actor", source_event["actor"]),
            ("target_type", source_event["target_type"]),
            ("target_id", source_event["target_id"]),
            ("room_id", source_event["room_id"]),
            ("classification_level", source_event["classification_level"]),
            ("created_at", source_event["created_at"]),
        ]

        event_type = source_event["event_type"]
        if event_type == "ingest_requested":
            return _stable_fact_string(
                common_fields
                + [
                    ("collection", _metadata_value(metadata, "collection")),
                    ("root_path", _metadata_value(metadata, "root_path")),
                ]
            )
        if event_type in {"dataset_registered", "dataset_updated"}:
            return _stable_fact_string(
                common_fields
                + [
                    ("dataset_id", self._extract_exact_int(metadata, "dataset_id")),
                    ("collection", _metadata_value(metadata, "collection")),
                    ("root_path", _metadata_value(metadata, "root_path")),
                    ("description", _metadata_value(metadata, "description")),
                ]
            )
        if event_type == "ingest_started":
            return _stable_fact_string(
                common_fields
                + [
                    ("dataset_id", self._extract_exact_int(metadata, "dataset_id")),
                    ("ingest_run_id", self._extract_exact_int(metadata, "ingest_run_id")),
                    ("files_discovered", self._extract_exact_int(metadata, "files_discovered")),
                ]
            )
        if event_type == "ingest_completed":
            return _stable_fact_string(
                common_fields
                + [
                    ("dataset_id", self._extract_exact_int(metadata, "dataset_id")),
                    ("ingest_run_id", self._extract_exact_int(metadata, "ingest_run_id")),
                    ("files_discovered", self._extract_exact_int(metadata, "files_discovered")),
                    ("assets_indexed", self._extract_exact_int(metadata, "assets_indexed")),
                    ("new_assets", self._extract_exact_int(metadata, "new_assets")),
                    ("updated_assets", self._extract_exact_int(metadata, "updated_assets")),
                    ("unchanged_assets", self._extract_exact_int(metadata, "unchanged_assets")),
                    ("duplicates_detected", self._extract_exact_int(metadata, "duplicates_detected")),
                    ("error_count", len(_metadata_value(metadata, "errors") or [])),
                ]
            )
        if event_type == "ingest_blocked":
            return _stable_fact_string(
                common_fields
                + [
                    ("guard_name", _metadata_value(metadata, "guard_name")),
                    ("decision", _metadata_value(metadata, "decision")),
                    ("requires_supervisor", _metadata_value(metadata, "requires_supervisor")),
                ]
            )
        return None

    def _extract_exact_int(
        self,
        metadata: Mapping[str, Any] | None,
        key: str,
    ) -> int | None:
        value = _metadata_value(metadata, key)
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
        return None

    def _normalize_correction_reason(self, reason: str) -> str:
        normalized = reason.strip()
        if not normalized:
            raise ValueError("Correction reason is required.")
        return normalized

    def _ensure_correction_access(self, *, room_id: str, actor_role: str) -> None:
        decision = access_guard.evaluate(
            room_id=room_id,
            actor_role=actor_role,
            requested_permission="write",
        )
        if decision.decision not in {"allowed", "requires_approval"}:
            raise PermissionError(decision.reason)

    def _log_correction_started(
        self,
        *,
        room_id: str,
        memory_kind: str,
        memory_id: str,
        operation: str,
        reason: str,
        actor_role: str,
        classification_level: str,
        superseded_by_id: int | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        self.audit_service.log_event(
            event_type="memory_correction_started",
            actor="hypervisor",
            target_type=f"memory_{memory_kind}",
            target_id=memory_id,
            room_id=room_id,
            classification_level=classification_level,
            summary="Memory correction started.",
            metadata=self._correction_audit_metadata(
                room_id=room_id,
                memory_kind=memory_kind,
                memory_id=memory_id,
                operation=operation,
                reason=reason,
                actor_role=actor_role,
                superseded_by_id=superseded_by_id,
            ),
            conn=conn,
        )

    def _log_correction_completed(
        self,
        *,
        result: MemoryCorrectionResult,
        reason: str,
        actor_role: str,
        classification_level: str,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        self.audit_service.log_event(
            event_type="memory_correction_completed",
            actor="hypervisor",
            target_type=f"memory_{result.memory_kind}",
            target_id=result.memory_id,
            room_id=result.room_id,
            classification_level=classification_level,
            summary="Memory correction completed.",
            metadata=self._correction_audit_metadata(
                room_id=result.room_id,
                memory_kind=result.memory_kind,
                memory_id=result.memory_id,
                operation=result.operation,
                reason=reason,
                actor_role=actor_role,
                previous_status=result.previous_status,
                resulting_status=result.resulting_status,
                superseded_by_id=result.superseded_by_id,
            ),
            conn=conn,
        )

    def _log_correction_blocked(
        self,
        *,
        room_id: str,
        memory_kind: str,
        memory_id: str,
        operation: str,
        reason: str,
        actor_role: str,
        classification_level: str,
        previous_status: str | None,
        resulting_status: str | None,
        superseded_by_id: int | None,
        block_reason: str,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        self.audit_service.log_event(
            event_type="memory_correction_blocked",
            actor="hypervisor",
            target_type=f"memory_{memory_kind}",
            target_id=memory_id,
            room_id=room_id,
            classification_level=classification_level,
            summary="Memory correction blocked.",
            metadata=self._correction_audit_metadata(
                room_id=room_id,
                memory_kind=memory_kind,
                memory_id=memory_id,
                operation=operation,
                reason=reason,
                actor_role=actor_role,
                previous_status=previous_status,
                resulting_status=resulting_status,
                superseded_by_id=superseded_by_id,
                extra={"block_reason": block_reason},
            ),
            conn=conn,
        )

    def _correction_audit_metadata(
        self,
        *,
        room_id: str,
        memory_kind: str,
        memory_id: str,
        operation: str,
        reason: str,
        actor_role: str,
        previous_status: str | None = None,
        resulting_status: str | None = None,
        superseded_by_id: int | None = None,
        extra: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "room_id": room_id,
            "memory_kind": memory_kind,
            "memory_id": memory_id,
            "operation": operation,
            "reason": reason,
            "actor_role": actor_role,
        }
        if previous_status is not None:
            metadata["previous_status"] = previous_status
        if resulting_status is not None:
            metadata["resulting_status"] = resulting_status
        if superseded_by_id is not None:
            metadata["superseded_by_id"] = superseded_by_id
        if extra:
            metadata.update(dict(extra))
        return metadata

    def _ensure_write_access(
        self,
        *,
        room_id: str,
        actor_role: str,
        result: MemorySeedResult,
        conn: sqlite3.Connection | None = None,
        mode: str,
    ) -> None:
        decision = access_guard.evaluate(
            room_id=room_id,
            actor_role=actor_role,
            requested_permission="write",
        )
        if decision.decision not in {"allowed", "requires_approval"}:
            raise PermissionError(decision.reason)

    def _ensure_room_classification(
        self,
        *,
        room_id: str,
        classification_level: str,
    ) -> None:
        decision = classification_guard.evaluate(
            room_id=room_id,
            classification_level=classification_level,
        )
        if decision.decision != "allowed":
            raise PermissionError(decision.reason)

    def _require_room(self, room_id: str):
        room = room_registry.get_room(room_id)
        if room is None:
            raise PermissionError(f"Room {room_id} is not registered.")
        return room

    def _log_batch_started(
        self,
        *,
        mode: str,
        room_id: str,
        ingest_run_id: int | None,
        seed_version: str,
        room_classification: str,
        metadata: Mapping[str, Any] | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        self.audit_service.log_event(
            event_type=f"memory_{mode}_started",
            actor="hypervisor",
            target_type="memory_room",
            target_id=room_id,
            room_id=room_id,
            classification_level=room_classification,
            summary=f"Memory {mode} started.",
            metadata=self._result_metadata(
                room_id=room_id,
                ingest_run_id=ingest_run_id,
                seed_version=seed_version,
                extra=metadata,
            ),
            conn=conn,
        )

    def _log_batch_completed(
        self,
        *,
        mode: str,
        room_id: str,
        ingest_run_id: int | None,
        room_classification: str,
        result: MemorySeedResult,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        self.audit_service.log_event(
            event_type=f"memory_{mode}_completed",
            actor="hypervisor",
            target_type="memory_room",
            target_id=room_id,
            room_id=room_id,
            classification_level=room_classification,
            summary=f"Memory {mode} completed.",
            metadata=self._result_metadata(
                room_id=room_id,
                ingest_run_id=ingest_run_id,
                seed_version=result.seed_version,
                result=result,
            ),
            conn=conn,
        )

    def _log_batch_blocked(
        self,
        *,
        mode: str,
        room_id: str,
        ingest_run_id: int | None,
        room_classification: str,
        reason: str,
        result: MemorySeedResult,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        self.audit_service.log_event(
            event_type=f"memory_{mode}_blocked",
            actor="hypervisor",
            target_type="memory_room",
            target_id=room_id,
            room_id=room_id,
            classification_level=room_classification,
            summary=f"Memory {mode} blocked.",
            metadata=self._result_metadata(
                room_id=room_id,
                ingest_run_id=ingest_run_id,
                seed_version=result.seed_version,
                result=result,
                extra={"reason": reason},
            ),
            conn=conn,
        )

    def _result_metadata(
        self,
        *,
        room_id: str,
        ingest_run_id: int | None,
        seed_version: str,
        result: MemorySeedResult | None = None,
        extra: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "room_id": room_id,
            "seed_version": seed_version,
        }
        if ingest_run_id is not None:
            metadata["ingest_run_id"] = ingest_run_id
        if result is not None:
            metadata.update(result.model_dump())
        if extra:
            metadata.update(dict(extra))
        return metadata
