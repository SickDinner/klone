from __future__ import annotations

from collections.abc import Mapping
import json
import sqlite3
from typing import Any

from .audit import AuditService
from .guards import access_guard, classification_guard
from .repository import KloneRepository
from .rooms import room_registry
from .schemas import (
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

    def get_event_detail(
        self,
        *,
        room_id: str,
        event_id: int,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any] | None:
        event_row = self.repository.get_memory_event(event_id, room_id=room_id)
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
        payload = _decode_row_metadata(event_row)
        payload["provenance"] = provenance
        payload["source_lineage"] = [
            row for row in provenance if row["provenance_type"] == "source_lineage"
        ]
        payload["seed_basis"] = [row for row in provenance if row["provenance_type"] == "seed_basis"]
        payload["linked_entities"] = linked_entities
        return payload

    def get_episode_detail(
        self,
        *,
        room_id: str,
        episode_id: str,
        conn: sqlite3.Connection | None = None,
    ) -> dict[str, Any] | None:
        episode_row = self.repository.get_memory_episode(episode_id, room_id=room_id)
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
