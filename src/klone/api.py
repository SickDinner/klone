from __future__ import annotations

from dataclasses import asdict
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from .blueprint import SYSTEM_BLUEPRINT
from .config import settings
from .guards import access_guard, governance_guard_catalog, output_guard
from .ingest import ingest_dataset
from .repository import KloneRepository
from .rooms import PERMISSION_LEVELS, room_registry
from .schemas import (
    AssetRecord,
    AuditEventRecord,
    DatasetIngestRequest,
    DatasetRecord,
    GovernanceGuardRecord,
    IngestExecutionResponse,
    IngestStatusResponse,
    MissionControlStatus,
    PermissionLevelRecord,
    RoomRecord,
)


router = APIRouter(prefix="/api")


def get_repository(request: Request) -> KloneRepository:
    return request.app.state.repository


def _resolve_rooms(
    *,
    requested_room_id: str | None,
    permission: str,
    accept_requires_approval: bool = False,
) -> list[RoomRecord]:
    if requested_room_id is not None:
        room = room_registry.get_room(requested_room_id)
        if room is None:
            raise HTTPException(status_code=404, detail=f"Room {requested_room_id} was not found.")
        decision = access_guard.evaluate(
            room_id=room.id,
            actor_role="owner",
            requested_permission=permission,
        )
        allowed_decisions = {"allowed", "requires_approval"} if accept_requires_approval else {"allowed"}
        if decision.decision not in allowed_decisions:
            raise HTTPException(status_code=403, detail=decision.reason)
        return [room]

    rooms: list[RoomRecord] = []
    for room in room_registry.list_rooms():
        decision = access_guard.evaluate(
            room_id=room.id,
            actor_role="owner",
            requested_permission=permission,
        )
        allowed_decisions = {"allowed", "requires_approval"} if accept_requires_approval else {"allowed"}
        if decision.decision in allowed_decisions:
            rooms.append(room)
    return rooms


def _decode_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    metadata_json = payload.pop("metadata_json", None)
    if metadata_json:
        payload["metadata"] = json.loads(metadata_json)
    return payload


def _asset_record_from_row(row: dict[str, Any]) -> AssetRecord:
    payload = _decode_metadata(dict(row))
    sanitized, _ = output_guard.sanitize_record(
        payload,
        classification_level=payload["classification_level"],
    )
    return AssetRecord.model_validate(sanitized)


def _dataset_record_from_row(row: dict[str, Any]) -> DatasetRecord:
    payload = dict(row)
    decision = output_guard.evaluate(classification_level=payload["classification_level"])
    if decision.decision == "summary_only":
        payload["root_path"] = "[summary-only]"
        payload["description"] = "summary_only"
    return DatasetRecord.model_validate(payload)


def _audit_event_from_row(row: dict[str, Any]) -> AuditEventRecord:
    payload = _decode_metadata(dict(row))
    decision = output_guard.evaluate(classification_level=payload["classification_level"])
    if decision.decision == "summary_only":
        payload["summary"] = "Summary-only event"
        payload["metadata"] = {"policy": "summary_only"}
    return AuditEventRecord.model_validate(payload)


@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "app": settings.app_name,
        "environment": settings.environment,
        "owner_debug_mode": settings.owner_debug_mode,
        "database_path": str(settings.sqlite_path),
    }


@router.get("/status", response_model=MissionControlStatus)
def status(repository: KloneRepository = Depends(get_repository)) -> MissionControlStatus:
    rooms = _resolve_rooms(requested_room_id=None, permission="discover")
    aggregate = {
        "dataset_count": 0,
        "asset_count": 0,
        "duplicate_count": 0,
        "audit_event_count": 0,
    }
    latest_candidates = []
    for room in rooms:
        room_counts = repository.counts_for_room(room_id=room.id)
        aggregate["dataset_count"] += room_counts["dataset_count"]
        aggregate["asset_count"] += room_counts["asset_count"]
        aggregate["duplicate_count"] += room_counts["duplicate_count"]
        aggregate["audit_event_count"] += room_counts["audit_event_count"]
        latest_run = repository.latest_ingest_run(room_id=room.id)
        if latest_run is not None:
            latest_candidates.append(latest_run)
    latest_ingest = (
        sorted(latest_candidates, key=lambda item: item["started_at"], reverse=True)[0]
        if latest_candidates
        else None
    )
    return MissionControlStatus(
        app_name=settings.app_name,
        environment=settings.environment,
        owner_debug_mode=settings.owner_debug_mode,
        database_path=str(settings.sqlite_path),
        dataset_count=aggregate["dataset_count"],
        indexed_asset_count=aggregate["asset_count"],
        duplicate_asset_count=aggregate["duplicate_count"],
        audit_event_count=aggregate["audit_event_count"],
        latest_ingest=latest_ingest,
        room_count=len(rooms),
        module_count=len(SYSTEM_BLUEPRINT.modules),
        agent_count=len(SYSTEM_BLUEPRINT.agents),
        guard_count=len(governance_guard_catalog()),
    )


@router.get("/blueprint")
def blueprint() -> dict:
    return SYSTEM_BLUEPRINT.to_dict()


@router.get("/modules")
def modules() -> list[dict]:
    return [asdict(module) for module in SYSTEM_BLUEPRINT.modules]


@router.get("/agents")
def agents() -> list[dict]:
    return [asdict(agent) for agent in SYSTEM_BLUEPRINT.agents]


@router.get("/phases")
def phases() -> list[dict]:
    return [asdict(phase) for phase in SYSTEM_BLUEPRINT.build_phases]


@router.get("/rooms", response_model=list[RoomRecord])
def rooms() -> list[RoomRecord]:
    return room_registry.list_rooms()


@router.get("/permission-levels", response_model=list[PermissionLevelRecord])
def permission_levels() -> list[PermissionLevelRecord]:
    return [PermissionLevelRecord.model_validate(asdict(permission)) for permission in PERMISSION_LEVELS]


@router.get("/governance/guards", response_model=list[GovernanceGuardRecord])
def governance_guards() -> list[GovernanceGuardRecord]:
    return governance_guard_catalog()


@router.get("/datasets", response_model=list[DatasetRecord])
def datasets(
    room_id: str | None = Query(default=None),
    repository: KloneRepository = Depends(get_repository),
) -> list[DatasetRecord]:
    records: list[DatasetRecord] = []
    for room in _resolve_rooms(requested_room_id=room_id, permission="discover"):
        records.extend(_dataset_record_from_row(row) for row in repository.list_datasets(room_id=room.id))
    return sorted(records, key=lambda item: item.updated_at, reverse=True)


@router.get("/assets", response_model=list[AssetRecord])
def assets(
    room_id: str | None = Query(default=None),
    dataset_id: int | None = Query(default=None),
    limit: int = Query(default=settings.asset_preview_limit, ge=1, le=200),
    repository: KloneRepository = Depends(get_repository),
) -> list[AssetRecord]:
    rows: list[dict[str, Any]] = []
    for room in _resolve_rooms(requested_room_id=room_id, permission="read"):
        rows.extend(
            repository.list_assets(
                room_id=room.id,
                dataset_id=dataset_id,
                limit=limit,
            )
        )
    rows = sorted(rows, key=lambda item: item["indexed_at"], reverse=True)[:limit]
    return [_asset_record_from_row(row) for row in rows]


@router.get("/assets/{asset_id}", response_model=AssetRecord)
def asset_detail(asset_id: int, repository: KloneRepository = Depends(get_repository)) -> AssetRecord:
    for room in _resolve_rooms(requested_room_id=None, permission="read"):
        row = repository.get_asset(asset_id, room_id=room.id)
        if row is not None:
            return _asset_record_from_row(row)
    raise HTTPException(status_code=404, detail=f"Asset {asset_id} was not found.")


@router.get("/ingest/status", response_model=IngestStatusResponse)
def ingest_status(
    room_id: str | None = Query(default=None),
    repository: KloneRepository = Depends(get_repository),
) -> IngestStatusResponse:
    recent_runs: list[dict[str, Any]] = []
    for room in _resolve_rooms(requested_room_id=room_id, permission="discover"):
        recent_runs.extend(repository.list_ingest_runs(room_id=room.id, limit=8))
    recent_runs = sorted(recent_runs, key=lambda item: item["started_at"], reverse=True)[:8]
    return IngestStatusResponse(
        queue_depth=0,
        latest_run=recent_runs[0] if recent_runs else None,
        recent_runs=recent_runs,
    )


@router.get("/audit", response_model=list[AuditEventRecord])
def audit(
    room_id: str | None = Query(default=None),
    limit: int = Query(default=settings.audit_preview_limit, ge=1, le=100),
    repository: KloneRepository = Depends(get_repository),
) -> list[AuditEventRecord]:
    rows: list[dict[str, Any]] = []
    for room in _resolve_rooms(requested_room_id=room_id, permission="summarize"):
        rows.extend(repository.list_audit_events(room_id=room.id, limit=limit))
    rows = sorted(rows, key=lambda item: item["created_at"], reverse=True)[:limit]
    return [_audit_event_from_row(row) for row in rows]


@router.post("/ingest/scan", response_model=IngestExecutionResponse)
def ingest_scan(
    request: DatasetIngestRequest,
    repository: KloneRepository = Depends(get_repository),
) -> IngestExecutionResponse:
    try:
        result = ingest_dataset(repository, request)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except NotADirectoryError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    except OSError as error:
        raise HTTPException(status_code=500, detail=f"Ingest failed: {error}") from error
    return IngestExecutionResponse.model_validate(result)
