from __future__ import annotations

from collections.abc import Mapping
import json
import sqlite3
from typing import Any

from .audit import AuditService
from .guards import access_guard, classification_guard
from .repository import KloneRepository
from .rooms import room_registry
from .schemas import MemorySeedResult


ELIGIBLE_AUDIT_EVENT_TYPES = {
    "dataset_registered",
    "dataset_updated",
    "ingest_requested",
    "ingest_started",
    "ingest_completed",
    "ingest_blocked",
}

SEED_VERSION = "phase_2b_1"
SYSTEM_ACTOR_CANONICAL_KEY = "system_actor:system"


def _decode_metadata(raw_metadata: str | None) -> dict[str, Any] | None:
    if not raw_metadata:
        return None
    return json.loads(raw_metadata)


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
        conn: sqlite3.Connection | None = None,
    ) -> MemorySeedResult:
        room = room_registry.get_room(room_id)
        if room is None:
            raise ValueError(f"Room {room_id} is not registered.")

        result = MemorySeedResult(
            room_id=room_id,
            ingest_run_id=ingest_run_id,
            seed_version=SEED_VERSION,
        )

        access_decision = access_guard.evaluate(
            room_id=room_id,
            actor_role="owner",
            requested_permission="write",
        )
        if access_decision.decision not in {"allowed", "requires_approval"}:
            self._log_seed_blocked(
                room_id=room_id,
                ingest_run_id=ingest_run_id,
                reason=access_decision.reason,
                counts=result,
                conn=conn,
            )
            raise PermissionError(access_decision.reason)

        self.audit_service.log_event(
            event_type="memory_seed_started",
            actor="hypervisor",
            target_type="memory_seed_batch",
            target_id=str(ingest_run_id) if ingest_run_id is not None else room_id,
            room_id=room_id,
            classification_level=room.classification,
            summary="Memory seed batch started.",
            metadata={
                "room_id": room_id,
                "ingest_run_id": ingest_run_id,
                "seed_version": SEED_VERSION,
                "audit_event_ids": audit_event_ids,
            },
            conn=conn,
        )

        try:
            source_events = self.repository.list_audit_events_by_ids(
                audit_event_ids,
                room_id=room_id,
                conn=conn,
            )

            memory_events: list[dict[str, Any]] = []
            for source_event in source_events:
                if source_event["event_type"] not in ELIGIBLE_AUDIT_EVENT_TYPES:
                    continue
                event_row = self._seed_event_from_audit_row(source_event, conn=conn)
                if event_row is None:
                    result.events_skipped += 1
                    continue
                created = event_row.pop("_created")
                if created:
                    result.events_written += 1
                else:
                    result.events_upserted += 1
                memory_events.append(event_row)

            for event_row in memory_events:
                for entity_payload, link_payload in self._build_event_entity_payloads(
                    event_row,
                    conn=conn,
                ):
                    entity_decision = classification_guard.evaluate(
                        classification_level=entity_payload["classification_level"],
                        room_id=entity_payload["room_id"],
                    )
                    if entity_decision.decision != "allowed":
                        raise PermissionError(entity_decision.reason)
                    entity_row, entity_created = self.repository.upsert_memory_entity(
                        entity_payload,
                        conn=conn,
                    )
                    if entity_created:
                        result.entities_written += 1
                    else:
                        result.entities_upserted += 1
                    link_decision = classification_guard.evaluate(
                        classification_level=event_row["classification_level"],
                        room_id=event_row["room_id"],
                    )
                    if link_decision.decision != "allowed":
                        raise PermissionError(link_decision.reason)
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

            if ingest_run_id is not None:
                episode_row = self._seed_ingest_run_episode(
                    room_id=room_id,
                    ingest_run_id=ingest_run_id,
                    conn=conn,
                )
                if episode_row is None:
                    result.episodes_skipped += 1
                else:
                    episode_created = episode_row.pop("_created")
                    if episode_created:
                        result.episodes_written += 1
                    else:
                        result.episodes_upserted += 1
                    linked_events = sorted(
                        [
                            event_row
                            for event_row in self.repository.list_memory_events_for_ingest_run(
                                room_id=room_id,
                                ingest_run_id=ingest_run_id,
                                conn=conn,
                            )
                        ],
                        key=lambda item: (
                            item["occurred_at"],
                            item["recorded_at"],
                            item["id"],
                        ),
                    )
                    for sequence_no, event_row in enumerate(linked_events, start=1):
                        link_decision = classification_guard.evaluate(
                            classification_level=event_row["classification_level"],
                            room_id=event_row["room_id"],
                        )
                        if link_decision.decision != "allowed":
                            raise PermissionError(link_decision.reason)
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
        except PermissionError as error:
            self._log_seed_blocked(
                room_id=room_id,
                ingest_run_id=ingest_run_id,
                reason=str(error),
                counts=result,
                conn=conn,
            )
            raise

        self.audit_service.log_event(
            event_type="memory_seed_completed",
            actor="hypervisor",
            target_type="memory_seed_batch",
            target_id=str(ingest_run_id) if ingest_run_id is not None else room_id,
            room_id=room_id,
            classification_level=room.classification,
            summary="Memory seed batch completed.",
            metadata=self._result_metadata(result),
            conn=conn,
        )
        return result

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

        classification_decision = classification_guard.evaluate(
            classification_level=classification_level,
            room_id=room_id,
        )
        if classification_decision.decision != "allowed":
            raise PermissionError(classification_decision.reason)

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

        room = room_registry.get_room(room_id)
        if room is None:
            return None

        classification_decision = classification_guard.evaluate(
            classification_level=room.classification,
            room_id=room_id,
        )
        if classification_decision.decision != "allowed":
            raise PermissionError(classification_decision.reason)

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

    def _build_evidence_text(
        self,
        source_event: Mapping[str, Any],
        metadata: Mapping[str, Any] | None,
    ) -> str | None:
        summary = source_event.get("summary")
        if isinstance(summary, str) and summary.strip():
            return summary
        fact_string = _stable_fact_string(
            [
                ("event_type", source_event.get("event_type")),
                ("actor", source_event.get("actor")),
                ("target_type", source_event.get("target_type")),
                ("target_id", source_event.get("target_id")),
                ("room_id", source_event.get("room_id")),
                ("classification_level", source_event.get("classification_level")),
                ("created_at", source_event.get("created_at")),
                ("metadata", metadata),
            ]
        )
        return fact_string or None

    def _extract_exact_int(self, metadata: Mapping[str, Any] | None, key: str) -> int | None:
        if metadata is None:
            return None
        value = metadata.get(key)
        return value if isinstance(value, int) else None

    def _log_seed_blocked(
        self,
        *,
        room_id: str,
        ingest_run_id: int | None,
        reason: str,
        counts: MemorySeedResult,
        conn: sqlite3.Connection | None = None,
    ) -> None:
        room = room_registry.get_room(room_id)
        if room is None:
            return
        self.audit_service.log_event(
            event_type="memory_seed_blocked",
            actor="hypervisor",
            target_type="memory_seed_batch",
            target_id=str(ingest_run_id) if ingest_run_id is not None else room_id,
            room_id=room_id,
            classification_level=room.classification,
            summary="Memory seed batch blocked.",
            metadata={
                **self._result_metadata(counts),
                "reason": reason,
            },
            conn=conn,
        )

    def _result_metadata(self, result: MemorySeedResult) -> dict[str, Any]:
        return {
            "room_id": result.room_id,
            "ingest_run_id": result.ingest_run_id,
            "seed_version": result.seed_version,
            "events_written": result.events_written,
            "events_upserted": result.events_upserted,
            "events_skipped": result.events_skipped,
            "entities_written": result.entities_written,
            "entities_upserted": result.entities_upserted,
            "entities_skipped": result.entities_skipped,
            "episodes_written": result.episodes_written,
            "episodes_upserted": result.episodes_upserted,
            "episodes_skipped": result.episodes_skipped,
            "event_entity_links_written": result.event_entity_links_written,
            "event_entity_links_upserted": result.event_entity_links_upserted,
            "event_entity_links_skipped": result.event_entity_links_skipped,
            "episode_event_links_written": result.episode_event_links_written,
            "episode_event_links_upserted": result.episode_event_links_upserted,
            "episode_event_links_skipped": result.episode_event_links_skipped,
        }
