from __future__ import annotations

from dataclasses import asdict
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from .blueprint import SYSTEM_BLUEPRINT
from .config import Settings, settings
from .contracts import APP_VERSION, MODULE_REGISTRY_VERSION, MemoryEpisodeType, MemoryStatus
from .guards import access_guard, governance_guard_catalog, output_guard
from .ingest import ingest_dataset
from .memory import MemoryService
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
    InternalRunRecord,
    MemoryEntityRecord,
    MemoryEpisodeDetailRecord,
    MemoryEpisodeProvenanceDetailRecord,
    MemoryEventEpisodeMembershipRecord,
    MemoryEpisodeMemberRecord,
    MemoryEpisodeRecord,
    MemoryContextCorrectionSummaryRecord,
    MemoryContextPackageRecord,
    MemoryContextQueryScopeRecord,
    MemoryContextSupersessionLinkRecord,
    MemoryEventDetailRecord,
    MemoryEventProvenanceDetailRecord,
    MemoryEventRecord,
    MemoryLinkedEntityRecord,
    MemoryLlmAnswerRecord,
    MemoryLlmAnswerSourceRecord,
    MemoryLlmContextExclusionRecord,
    MemoryLlmContextInclusionRecord,
    MemoryLlmContextPayloadRecord,
    MemoryProvenanceRecord,
    MemoryProvenanceSummaryRecord,
    MemoryEventSupersessionRecord,
    ModuleCapabilityRecord,
    MissionControlStatus,
    PermissionLevelRecord,
    BootstrapStatusRecord,
    RoomRecord,
    RuntimeConfigRecord,
)


router = APIRouter(prefix="/api")


def get_repository(request: Request) -> KloneRepository:
    return request.app.state.repository


def get_runtime_settings(request: Request) -> Settings:
    return getattr(request.app.state, "settings", settings)


def get_bootstrap_report(request: Request, repository: KloneRepository | None = None) -> dict[str, Any]:
    state_report = getattr(request.app.state, "bootstrap_report", None)
    if state_report is not None:
        return dict(state_report)
    if repository is None:
        repository = get_repository(request)
    return repository.bootstrap_report()


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


def _memory_event_from_row(row: dict[str, Any]) -> MemoryEventRecord:
    payload = _decode_metadata(dict(row))
    decision = output_guard.evaluate(classification_level=payload["classification_level"])
    if decision.decision == "summary_only":
        payload["evidence_text"] = "[summary-only]"
        payload["metadata"] = {"policy": "summary_only"}
    return MemoryEventRecord.model_validate(payload)


def _memory_entity_from_row(row: dict[str, Any]) -> MemoryEntityRecord:
    payload = _decode_metadata(dict(row))
    decision = output_guard.evaluate(classification_level=payload["classification_level"])
    if decision.decision == "summary_only":
        payload["canonical_name"] = "[summary-only]"
        payload["metadata"] = {"policy": "summary_only"}
    return MemoryEntityRecord.model_validate(payload)


def _memory_episode_from_row(row: dict[str, Any]) -> MemoryEpisodeRecord:
    payload = _decode_metadata(dict(row))
    decision = output_guard.evaluate(classification_level=payload["classification_level"])
    if decision.decision == "summary_only":
        payload["summary"] = "[summary-only]"
        payload["metadata"] = {"policy": "summary_only"}
    return MemoryEpisodeRecord.model_validate(payload)


def _memory_provenance_from_row(row: dict[str, Any]) -> MemoryProvenanceRecord:
    return MemoryProvenanceRecord.model_validate(dict(row))


def _memory_linked_entity_from_row(row: dict[str, Any]) -> MemoryLinkedEntityRecord:
    payload = dict(row)
    decision = output_guard.evaluate(classification_level=payload["classification_level"])
    if decision.decision == "summary_only":
        payload["canonical_name"] = "[summary-only]"
        payload["metadata"] = {"policy": "summary_only"}
    return MemoryLinkedEntityRecord.model_validate(payload)


def _memory_provenance_summary_from_payload(payload: dict[str, Any]) -> MemoryProvenanceSummaryRecord:
    return MemoryProvenanceSummaryRecord.model_validate(payload)


def _memory_event_supersession_from_payload(payload: dict[str, Any]) -> MemoryEventSupersessionRecord:
    return MemoryEventSupersessionRecord.model_validate(payload)


def _memory_event_episode_membership_from_payload(
    payload: dict[str, Any],
) -> MemoryEventEpisodeMembershipRecord:
    return MemoryEventEpisodeMembershipRecord.model_validate(
        {
            "sequence_no": payload["sequence_no"],
            "inclusion_basis": payload["inclusion_basis"],
            "episode": _memory_episode_from_row(payload["episode"]),
        }
    )


def _memory_event_detail_from_payload(payload: dict[str, Any]) -> MemoryEventDetailRecord:
    decision = output_guard.evaluate(classification_level=payload["classification_level"])
    hydrated = dict(payload)
    if decision.decision == "summary_only":
        hydrated["evidence_text"] = "[summary-only]"
        hydrated["metadata"] = {"policy": "summary_only"}
    hydrated["source_lineage"] = [
        _memory_provenance_from_row(item) for item in hydrated.get("source_lineage", [])
    ]
    hydrated["seed_basis"] = [
        _memory_provenance_from_row(item) for item in hydrated.get("seed_basis", [])
    ]
    hydrated["provenance"] = [
        _memory_provenance_from_row(item) for item in hydrated.get("provenance", [])
    ]
    hydrated["provenance_summary"] = _memory_provenance_summary_from_payload(
        hydrated.get("provenance_summary", {})
    )
    hydrated["linked_entities"] = [
        _memory_linked_entity_from_row(item) for item in hydrated.get("linked_entities", [])
    ]
    hydrated["episode_memberships"] = [
        _memory_event_episode_membership_from_payload(item)
        for item in hydrated.get("episode_memberships", [])
    ]
    hydrated["supersession_relationships"] = [
        _memory_event_supersession_from_payload(item)
        for item in hydrated.get("supersession_relationships", [])
    ]
    return MemoryEventDetailRecord.model_validate(hydrated)


def _memory_episode_member_from_payload(payload: dict[str, Any]) -> MemoryEpisodeMemberRecord:
    return MemoryEpisodeMemberRecord.model_validate(
        {
            "sequence_no": payload["sequence_no"],
            "inclusion_basis": payload["inclusion_basis"],
            "event": _memory_event_from_row(payload["event"]),
        }
    )


def _memory_episode_detail_from_payload(payload: dict[str, Any]) -> MemoryEpisodeDetailRecord:
    decision = output_guard.evaluate(classification_level=payload["classification_level"])
    hydrated = dict(payload)
    if decision.decision == "summary_only":
        hydrated["summary"] = "[summary-only]"
        hydrated["metadata"] = {"policy": "summary_only"}
    hydrated["source_lineage"] = [
        _memory_provenance_from_row(item) for item in hydrated.get("source_lineage", [])
    ]
    hydrated["seed_basis"] = [
        _memory_provenance_from_row(item) for item in hydrated.get("seed_basis", [])
    ]
    hydrated["membership_basis"] = [
        _memory_provenance_from_row(item) for item in hydrated.get("membership_basis", [])
    ]
    hydrated["provenance"] = [
        _memory_provenance_from_row(item) for item in hydrated.get("provenance", [])
    ]
    hydrated["provenance_summary"] = _memory_provenance_summary_from_payload(
        hydrated.get("provenance_summary", {})
    )
    hydrated["linked_events"] = [
        _memory_episode_member_from_payload(item) for item in hydrated.get("linked_events", [])
    ]
    return MemoryEpisodeDetailRecord.model_validate(hydrated)


def _memory_event_provenance_detail_from_payload(
    payload: dict[str, Any],
) -> MemoryEventProvenanceDetailRecord:
    hydrated = dict(payload)
    hydrated["event"] = _memory_event_from_row(hydrated["event"])
    hydrated["provenance"] = [
        _memory_provenance_from_row(item) for item in hydrated.get("provenance", [])
    ]
    hydrated["source_lineage"] = [
        _memory_provenance_from_row(item) for item in hydrated.get("source_lineage", [])
    ]
    hydrated["seed_basis"] = [
        _memory_provenance_from_row(item) for item in hydrated.get("seed_basis", [])
    ]
    hydrated["provenance_summary"] = _memory_provenance_summary_from_payload(
        hydrated.get("provenance_summary", {})
    )
    return MemoryEventProvenanceDetailRecord.model_validate(hydrated)


def _memory_episode_provenance_detail_from_payload(
    payload: dict[str, Any],
) -> MemoryEpisodeProvenanceDetailRecord:
    hydrated = dict(payload)
    hydrated["episode"] = _memory_episode_from_row(hydrated["episode"])
    hydrated["provenance"] = [
        _memory_provenance_from_row(item) for item in hydrated.get("provenance", [])
    ]
    hydrated["source_lineage"] = [
        _memory_provenance_from_row(item) for item in hydrated.get("source_lineage", [])
    ]
    hydrated["seed_basis"] = [
        _memory_provenance_from_row(item) for item in hydrated.get("seed_basis", [])
    ]
    hydrated["membership_basis"] = [
        _memory_provenance_from_row(item) for item in hydrated.get("membership_basis", [])
    ]
    hydrated["provenance_summary"] = _memory_provenance_summary_from_payload(
        hydrated.get("provenance_summary", {})
    )
    return MemoryEpisodeProvenanceDetailRecord.model_validate(hydrated)


def _memory_context_query_scope_from_payload(payload: dict[str, Any]) -> MemoryContextQueryScopeRecord:
    return MemoryContextQueryScopeRecord.model_validate(payload)


def _memory_context_supersession_from_payload(
    payload: dict[str, Any],
) -> MemoryContextSupersessionLinkRecord:
    return MemoryContextSupersessionLinkRecord.model_validate(payload)


def _memory_context_correction_summary_from_payload(
    payload: dict[str, Any],
) -> MemoryContextCorrectionSummaryRecord:
    hydrated = dict(payload)
    hydrated["supersession_links"] = [
        _memory_context_supersession_from_payload(item)
        for item in hydrated.get("supersession_links", [])
    ]
    return MemoryContextCorrectionSummaryRecord.model_validate(hydrated)


def _memory_context_package_from_payload(payload: dict[str, Any]) -> MemoryContextPackageRecord:
    hydrated = dict(payload)
    hydrated["query_scope"] = _memory_context_query_scope_from_payload(hydrated["query_scope"])
    hydrated["included_events"] = [
        _memory_event_detail_from_payload(item) for item in hydrated.get("included_events", [])
    ]
    hydrated["included_episodes"] = [
        _memory_episode_detail_from_payload(item)
        for item in hydrated.get("included_episodes", [])
    ]
    hydrated["provenance_summary"] = _memory_provenance_summary_from_payload(
        hydrated.get("provenance_summary", {})
    )
    hydrated["correction_summary"] = _memory_context_correction_summary_from_payload(
        hydrated.get("correction_summary", {})
    )
    return MemoryContextPackageRecord.model_validate(hydrated)


def _memory_llm_context_payload_from_payload(
    payload: dict[str, Any],
) -> MemoryLlmContextPayloadRecord:
    hydrated = dict(payload)
    hydrated["query_scope"] = _memory_context_query_scope_from_payload(hydrated["query_scope"])
    hydrated["context_package"] = _memory_context_package_from_payload(hydrated["context_package"])
    hydrated["included_context"] = [
        MemoryLlmContextInclusionRecord.model_validate(item)
        for item in hydrated.get("included_context", [])
    ]
    hydrated["excluded_context"] = [
        MemoryLlmContextExclusionRecord.model_validate(item)
        for item in hydrated.get("excluded_context", [])
    ]
    return MemoryLlmContextPayloadRecord.model_validate(hydrated)


def _memory_llm_answer_from_payload(payload: dict[str, Any]) -> MemoryLlmAnswerRecord:
    hydrated = dict(payload)
    hydrated["query_scope"] = _memory_context_query_scope_from_payload(hydrated["query_scope"])
    hydrated["context_payload"] = _memory_llm_context_payload_from_payload(hydrated["context_payload"])
    hydrated["source_backed_content"] = [
        MemoryLlmAnswerSourceRecord.model_validate(item)
        for item in hydrated.get("source_backed_content", [])
    ]
    return MemoryLlmAnswerRecord.model_validate(hydrated)


def _internal_run_from_row(row: dict[str, Any]) -> InternalRunRecord:
    payload = _decode_metadata(dict(row))
    return InternalRunRecord.model_validate(payload)


def _module_registry_payload() -> list[ModuleCapabilityRecord]:
    return [
        ModuleCapabilityRecord(
            id=module.id,
            name=module.name,
            stage=module.stage,
            status=module.status,
            supervisor=module.supervisor,
            key_inputs=list(module.key_inputs),
            outputs=list(module.outputs),
            capability_count=len(module.key_inputs) + len(module.outputs),
        )
        for module in SYSTEM_BLUEPRINT.modules
    ]


def _resolve_memory_scope(
    *,
    event_id: int | None,
    episode_id: str | None,
) -> tuple[int | None, str | None]:
    if (event_id is None) == (episode_id is None):
        raise HTTPException(status_code=400, detail="Exactly one of event_id or episode_id is required.")
    return event_id, episode_id


def _memory_service_http_error(error: ValueError) -> HTTPException:
    message = str(error)
    if "was not found" in message:
        return HTTPException(status_code=404, detail=message)
    return HTTPException(status_code=400, detail=message)


@router.get("/health")
def health(request: Request, repository: KloneRepository = Depends(get_repository)) -> dict:
    runtime_settings = get_runtime_settings(request)
    bootstrap = get_bootstrap_report(request, repository)
    latest_internal_run = repository.latest_internal_run()
    return {
        "status": "ok",
        "app": runtime_settings.app_name,
        "app_version": APP_VERSION,
        "environment": runtime_settings.environment,
        "owner_debug_mode": runtime_settings.owner_debug_mode,
        "database_path": str(runtime_settings.sqlite_path),
        "bootstrap_version": bootstrap["bootstrap_version"],
        "schema_version": bootstrap["schema_version"],
        "schema_user_version": bootstrap["schema_user_version"],
        "bootstrap_mode": bootstrap["bootstrap_mode"],
        "correction_schema_ready": bootstrap["correction_schema_ready"],
        "latest_internal_run_id": latest_internal_run["id"] if latest_internal_run is not None else None,
        "latest_internal_run_status": (
            latest_internal_run["status"] if latest_internal_run is not None else None
        ),
        "latest_internal_trace_id": (
            latest_internal_run["trace_id"] if latest_internal_run is not None else None
        ),
    }


@router.get("/status", response_model=MissionControlStatus)
def status(request: Request, repository: KloneRepository = Depends(get_repository)) -> MissionControlStatus:
    runtime_settings = get_runtime_settings(request)
    bootstrap = get_bootstrap_report(request, repository)
    module_registry = _module_registry_payload()
    recent_internal_runs = [_internal_run_from_row(row) for row in repository.list_internal_runs(limit=8)]
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
        app_name=runtime_settings.app_name,
        app_version=APP_VERSION,
        environment=runtime_settings.environment,
        owner_debug_mode=runtime_settings.owner_debug_mode,
        database_path=str(runtime_settings.sqlite_path),
        schema_version=bootstrap["schema_version"],
        bootstrap_version=bootstrap["bootstrap_version"],
        module_registry_version=MODULE_REGISTRY_VERSION,
        dataset_count=aggregate["dataset_count"],
        indexed_asset_count=aggregate["asset_count"],
        duplicate_asset_count=aggregate["duplicate_count"],
        audit_event_count=aggregate["audit_event_count"],
        latest_ingest=latest_ingest,
        room_count=len(rooms),
        module_count=len(SYSTEM_BLUEPRINT.modules),
        agent_count=len(SYSTEM_BLUEPRINT.agents),
        guard_count=len(governance_guard_catalog()),
        runtime_config=RuntimeConfigRecord.model_validate(runtime_settings.runtime_snapshot()),
        bootstrap=BootstrapStatusRecord.model_validate(bootstrap),
        module_registry=module_registry,
        latest_internal_run=recent_internal_runs[0] if recent_internal_runs else None,
        recent_internal_runs=recent_internal_runs,
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


@router.get("/memory/events", response_model=list[MemoryEventRecord])
def memory_events(
    room_id: str = Query(..., min_length=1),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status: MemoryStatus | None = Query(default=None),
    event_type: str | None = Query(default=None, min_length=1),
    ingest_run_id: int | None = Query(default=None, ge=1),
    include_corrected: bool = Query(default=True),
    repository: KloneRepository = Depends(get_repository),
) -> list[MemoryEventRecord]:
    room = _resolve_rooms(requested_room_id=room_id, permission="read")[0]
    rows = MemoryService(repository).query_events(
        room_id=room.id,
        limit=limit,
        offset=offset,
        status=status,
        event_type=event_type,
        ingest_run_id=ingest_run_id,
        include_corrected=include_corrected,
    )
    return [_memory_event_from_row(row) for row in rows]


@router.get("/memory/events/{event_id}", response_model=MemoryEventDetailRecord)
def memory_event_detail(
    event_id: int,
    room_id: str = Query(..., min_length=1),
    repository: KloneRepository = Depends(get_repository),
) -> MemoryEventDetailRecord:
    room = _resolve_rooms(requested_room_id=room_id, permission="read")[0]
    payload = MemoryService(repository).get_event_detail(room_id=room.id, event_id=event_id)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"Memory event {event_id} was not found.")
    return _memory_event_detail_from_payload(payload)


@router.get("/memory/events/{event_id}/provenance", response_model=MemoryEventProvenanceDetailRecord)
def memory_event_provenance_detail(
    event_id: int,
    room_id: str = Query(..., min_length=1),
    repository: KloneRepository = Depends(get_repository),
) -> MemoryEventProvenanceDetailRecord:
    room = _resolve_rooms(requested_room_id=room_id, permission="read")[0]
    payload = MemoryService(repository).get_event_provenance_detail(room_id=room.id, event_id=event_id)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"Memory event {event_id} was not found.")
    return _memory_event_provenance_detail_from_payload(payload)


@router.get("/memory/entities", response_model=list[MemoryEntityRecord])
def memory_entities(
    room_id: str = Query(..., min_length=1),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    repository: KloneRepository = Depends(get_repository),
) -> list[MemoryEntityRecord]:
    room = _resolve_rooms(requested_room_id=room_id, permission="read")[0]
    rows = repository.list_memory_entities(room_id=room.id, limit=limit, offset=offset)
    return [_memory_entity_from_row(row) for row in rows]


@router.get("/memory/entities/{entity_id}", response_model=MemoryEntityRecord)
def memory_entity_detail(
    entity_id: int,
    room_id: str = Query(..., min_length=1),
    repository: KloneRepository = Depends(get_repository),
) -> MemoryEntityRecord:
    room = _resolve_rooms(requested_room_id=room_id, permission="read")[0]
    row = repository.get_memory_entity(entity_id, room_id=room.id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Memory entity {entity_id} was not found.")
    return _memory_entity_from_row(row)


@router.get("/memory/episodes", response_model=list[MemoryEpisodeRecord])
def memory_episodes(
    room_id: str = Query(..., min_length=1),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status: MemoryStatus | None = Query(default=None),
    episode_type: MemoryEpisodeType | None = Query(default=None),
    ingest_run_id: int | None = Query(default=None, ge=1),
    include_corrected: bool = Query(default=True),
    repository: KloneRepository = Depends(get_repository),
) -> list[MemoryEpisodeRecord]:
    room = _resolve_rooms(requested_room_id=room_id, permission="read")[0]
    rows = MemoryService(repository).query_episodes(
        room_id=room.id,
        limit=limit,
        offset=offset,
        status=status,
        episode_type=episode_type,
        ingest_run_id=ingest_run_id,
        include_corrected=include_corrected,
    )
    return [_memory_episode_from_row(row) for row in rows]


@router.get("/memory/episodes/{episode_id}", response_model=MemoryEpisodeDetailRecord)
def memory_episode_detail(
    episode_id: str,
    room_id: str = Query(..., min_length=1),
    repository: KloneRepository = Depends(get_repository),
) -> MemoryEpisodeDetailRecord:
    room = _resolve_rooms(requested_room_id=room_id, permission="read")[0]
    payload = MemoryService(repository).get_episode_detail(room_id=room.id, episode_id=episode_id)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"Memory episode {episode_id} was not found.")
    return _memory_episode_detail_from_payload(payload)


@router.get(
    "/memory/episodes/{episode_id}/provenance",
    response_model=MemoryEpisodeProvenanceDetailRecord,
)
def memory_episode_provenance_detail(
    episode_id: str,
    room_id: str = Query(..., min_length=1),
    repository: KloneRepository = Depends(get_repository),
) -> MemoryEpisodeProvenanceDetailRecord:
    room = _resolve_rooms(requested_room_id=room_id, permission="read")[0]
    payload = MemoryService(repository).get_episode_provenance_detail(
        room_id=room.id,
        episode_id=episode_id,
    )
    if payload is None:
        raise HTTPException(status_code=404, detail=f"Memory episode {episode_id} was not found.")
    return _memory_episode_provenance_detail_from_payload(payload)


@router.get("/memory/episodes/{episode_id}/events", response_model=list[MemoryEpisodeMemberRecord])
def memory_episode_events(
    episode_id: str,
    room_id: str = Query(..., min_length=1),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    repository: KloneRepository = Depends(get_repository),
) -> list[MemoryEpisodeMemberRecord]:
    room = _resolve_rooms(requested_room_id=room_id, permission="read")[0]
    if repository.get_memory_episode(episode_id, room_id=room.id) is None:
        raise HTTPException(status_code=404, detail=f"Memory episode {episode_id} was not found.")
    members = MemoryService(repository).list_episode_members(
        room_id=room.id,
        episode_id=episode_id,
        limit=limit,
        offset=offset,
    )
    return [_memory_episode_member_from_payload(item) for item in members]


@router.get("/memory/context/package", response_model=MemoryContextPackageRecord)
def memory_context_package(
    room_id: str = Query(..., min_length=1),
    event_id: int | None = Query(default=None, ge=1),
    episode_id: str | None = Query(default=None, min_length=1),
    repository: KloneRepository = Depends(get_repository),
) -> MemoryContextPackageRecord:
    room = _resolve_rooms(requested_room_id=room_id, permission="read")[0]
    event_id, episode_id = _resolve_memory_scope(event_id=event_id, episode_id=episode_id)
    try:
        package = MemoryService(repository).assemble_context_package(
            room_id=room.id,
            event_id=event_id,
            episode_id=episode_id,
        )
    except ValueError as error:
        raise _memory_service_http_error(error) from error
    return _memory_context_package_from_payload(package.model_dump(mode="json"))


@router.get("/memory/context/payload", response_model=MemoryLlmContextPayloadRecord)
def memory_context_payload(
    room_id: str = Query(..., min_length=1),
    event_id: int | None = Query(default=None, ge=1),
    episode_id: str | None = Query(default=None, min_length=1),
    repository: KloneRepository = Depends(get_repository),
) -> MemoryLlmContextPayloadRecord:
    room = _resolve_rooms(requested_room_id=room_id, permission="read")[0]
    event_id, episode_id = _resolve_memory_scope(event_id=event_id, episode_id=episode_id)
    try:
        payload = MemoryService(repository).prepare_llm_context_payload(
            room_id=room.id,
            event_id=event_id,
            episode_id=episode_id,
        )
    except ValueError as error:
        raise _memory_service_http_error(error) from error
    return _memory_llm_context_payload_from_payload(payload.model_dump(mode="json"))


@router.get("/memory/context/answer", response_model=MemoryLlmAnswerRecord)
def memory_context_answer(
    question: str = Query(..., min_length=1, max_length=240),
    room_id: str = Query(..., min_length=1),
    event_id: int | None = Query(default=None, ge=1),
    episode_id: str | None = Query(default=None, min_length=1),
    repository: KloneRepository = Depends(get_repository),
) -> MemoryLlmAnswerRecord:
    room = _resolve_rooms(requested_room_id=room_id, permission="read")[0]
    event_id, episode_id = _resolve_memory_scope(event_id=event_id, episode_id=episode_id)
    try:
        answer = MemoryService(repository).generate_read_only_llm_answer(
            room_id=room.id,
            question=question,
            event_id=event_id,
            episode_id=episode_id,
        )
    except ValueError as error:
        raise _memory_service_http_error(error) from error
    return _memory_llm_answer_from_payload(answer.model_dump(mode="json"))


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
