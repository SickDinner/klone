from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from .api import (
    _asset_record_from_row,
    _dataset_record_from_row,
    _memory_episode_from_row,
    _memory_episode_detail_from_payload,
    _memory_event_from_row,
    _memory_event_detail_from_payload,
)
from .guards import access_guard
from .request_context import RequestContext
from .rooms import room_registry
from .schemas import (
    ObjectEnvelopeRecord,
    PublicCapabilitiesResponse,
    PublicObjectGetRequest,
    PublicObjectGetResponse,
    PublicQueryRequest,
    PublicQueryResponse,
    RequestContextRecord,
)
from .services import ServiceContainer, module_registry_payload
from .v1_contracts import contract_registry_payload


router = APIRouter(prefix="/v1")


def get_service_container(request: Request) -> ServiceContainer:
    return request.app.state.services


def get_request_context(request: Request) -> RequestContext:
    return request.state.request_context


def _require_room_read(*, room_id: str, actor_role: str) -> None:
    room = room_registry.get_room(room_id)
    if room is None:
        raise HTTPException(status_code=404, detail=f"Room {room_id} was not found.")
    decision = access_guard.evaluate(
        room_id=room_id,
        actor_role=actor_role,
        requested_permission="read",
    )
    if decision.decision != "allowed":
        raise HTTPException(status_code=403, detail=decision.reason)


def _sanitize_object_envelope(envelope: ObjectEnvelopeRecord) -> ObjectEnvelopeRecord:
    record_payload = dict(envelope.record)
    if envelope.object_kind == "dataset":
        sanitized_record = _dataset_record_from_row(record_payload).model_dump(mode="json")
    elif envelope.object_kind == "asset":
        sanitized_record = _asset_record_from_row(record_payload).model_dump(mode="json")
    elif envelope.object_kind == "memory_event":
        sanitized_record = _memory_event_detail_from_payload(record_payload).model_dump(mode="json")
    elif envelope.object_kind == "memory_episode":
        sanitized_record = _memory_episode_detail_from_payload(record_payload).model_dump(mode="json")
    else:
        raise HTTPException(status_code=400, detail="Unsupported object kind for public object get.")
    return envelope.model_copy(update={"record": sanitized_record})


@router.get("/capabilities", response_model=PublicCapabilitiesResponse)
def capabilities(
    services: ServiceContainer = Depends(get_service_container),
    request_context: RequestContext = Depends(get_request_context),
) -> PublicCapabilitiesResponse:
    contract_registry = contract_registry_payload()
    capabilities_payload = services.public_capabilities()
    response = PublicCapabilitiesResponse(
        api_version="v1",
        request_context=RequestContextRecord(
            request_id=request_context.request_id,
            trace_id=request_context.trace_id,
            principal=request_context.principal,
            actor_role=request_context.actor_role,
        ),
        services=services.seam_descriptors(),
        module_registry=module_registry_payload(),
        capabilities=capabilities_payload,
        contracts=contract_registry,
    )
    services.audit.log_control_plane_event(
        event_type="v1_capabilities_read",
        route_path="/v1/capabilities",
        request_context=request_context,
        status_code=200,
        summary="Read the public v1 capabilities seam.",
        metadata={
            "capability_count": len(capabilities_payload),
            "contract_count": len(contract_registry),
            "service_count": len(response.services),
        },
    )
    return response


@router.post("/rooms/{room_id}/objects/get", response_model=PublicObjectGetResponse)
def object_get(
    room_id: str,
    payload: PublicObjectGetRequest,
    services: ServiceContainer = Depends(get_service_container),
    request_context: RequestContext = Depends(get_request_context),
) -> PublicObjectGetResponse:
    route_path = f"/v1/rooms/{room_id}/objects/get"
    try:
        _require_room_read(room_id=room_id, actor_role=request_context.actor_role)
        envelope = services.object_envelope.get_object_envelope(
            room_id=room_id,
            object_id=payload.object_id,
        )
        if envelope is None:
            services.audit.log_control_plane_event(
                event_type="v1_object_get",
                route_path=route_path,
                request_context=request_context,
                status_code=404,
                summary="Attempted to read a public room-scoped object envelope that was not found.",
                metadata={"room_id": room_id, "object_id": payload.object_id, "result": "not_found"},
            )
            raise HTTPException(status_code=404, detail=f"Object {payload.object_id} was not found.")

        sanitized_envelope = _sanitize_object_envelope(envelope)
        response = PublicObjectGetResponse(
            api_version="v1",
            request_context=RequestContextRecord(
                request_id=request_context.request_id,
                trace_id=request_context.trace_id,
                principal=request_context.principal,
                actor_role=request_context.actor_role,
            ),
            room_id=room_id,
            object=sanitized_envelope,
        )
        services.audit.log_control_plane_event(
            event_type="v1_object_get",
            route_path=route_path,
            request_context=request_context,
            status_code=200,
            summary="Read a public room-scoped object envelope.",
            metadata={
                "room_id": room_id,
                "object_id": payload.object_id,
                "object_kind": sanitized_envelope.object_kind,
                "backing_route_count": len(sanitized_envelope.backing_routes),
                "result": "ok",
            },
        )
        return response
    except HTTPException as error:
        if error.status_code in {400, 403}:
            services.audit.log_control_plane_event(
                event_type="v1_object_get",
                route_path=route_path,
                request_context=request_context,
                status_code=error.status_code,
                summary="Blocked or invalid public room-scoped object envelope read.",
                metadata={
                    "room_id": room_id,
                    "object_id": payload.object_id,
                    "result": "error",
                    "detail": error.detail,
                },
            )
        raise
    except ValueError as error:
        services.audit.log_control_plane_event(
            event_type="v1_object_get",
            route_path=route_path,
            request_context=request_context,
            status_code=400,
            summary="Rejected invalid public room-scoped object envelope read.",
            metadata={
                "room_id": room_id,
                "object_id": payload.object_id,
                "result": "invalid_object_id",
                "detail": str(error),
            },
        )
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/rooms/{room_id}/query", response_model=PublicQueryResponse)
def query(
    room_id: str,
    payload: PublicQueryRequest,
    services: ServiceContainer = Depends(get_service_container),
    request_context: RequestContext = Depends(get_request_context),
) -> PublicQueryResponse:
    route_path = f"/v1/rooms/{room_id}/query"
    try:
        _require_room_read(room_id=room_id, actor_role=request_context.actor_role)
        if payload.query_kind == "memory_events":
            rows = services.memory.memory_service.query_events(
                room_id=room_id,
                limit=payload.limit,
                offset=payload.offset,
                status=payload.status,
                event_type=payload.event_type,
                ingest_run_id=payload.ingest_run_id,
                include_corrected=payload.include_corrected,
            )
            filters = {
                "status": payload.status,
                "event_type": payload.event_type,
                "ingest_run_id": payload.ingest_run_id,
                "include_corrected": payload.include_corrected,
            }
            backing_routes = ["/api/memory/events"]
            sanitized_results = [
                _memory_event_from_row(dict(row)).model_dump(mode="json")
                for row in rows
            ]
        elif payload.query_kind == "memory_episodes":
            rows = services.memory.memory_service.query_episodes(
                room_id=room_id,
                limit=payload.limit,
                offset=payload.offset,
                status=payload.status,
                episode_type=payload.episode_type,
                ingest_run_id=payload.ingest_run_id,
                include_corrected=payload.include_corrected,
            )
            filters = {
                "status": payload.status,
                "episode_type": payload.episode_type,
                "ingest_run_id": payload.ingest_run_id,
                "include_corrected": payload.include_corrected,
            }
            backing_routes = ["/api/memory/episodes"]
            sanitized_results = [
                _memory_episode_from_row(dict(row)).model_dump(mode="json")
                for row in rows
            ]
        else:
            raise HTTPException(
                status_code=400,
                detail="Unsupported query_kind. Supported kinds are memory_events and memory_episodes.",
            )

        applied_filters = {
            key: value
            for key, value in filters.items()
            if value is not None
        }
        response = PublicQueryResponse(
            api_version="v1",
            request_context=RequestContextRecord(
                request_id=request_context.request_id,
                trace_id=request_context.trace_id,
                principal=request_context.principal,
                actor_role=request_context.actor_role,
            ),
            room_id=room_id,
            query_id=f"query:{request_context.request_id}",
            query_kind=payload.query_kind,
            read_only=True,
            limit=payload.limit,
            offset=payload.offset,
            result_count=len(sanitized_results),
            filters=applied_filters,
            backing_routes=backing_routes,
            results=sanitized_results,
        )
        services.audit.log_control_plane_event(
            event_type="v1_query_read",
            route_path=route_path,
            request_context=request_context,
            status_code=200,
            summary="Executed a room-scoped public read-only query.",
            metadata={
                "room_id": room_id,
                "query_kind": payload.query_kind,
                "result_count": len(sanitized_results),
                "limit": payload.limit,
                "offset": payload.offset,
            },
        )
        return response
    except HTTPException as error:
        services.audit.log_control_plane_event(
            event_type="v1_query_read",
            route_path=route_path,
            request_context=request_context,
            status_code=error.status_code,
            summary="Blocked or invalid public room-scoped query.",
            metadata={
                "room_id": room_id,
                "query_kind": payload.query_kind,
                "limit": payload.limit,
                "offset": payload.offset,
                "result": "error",
                "detail": error.detail,
            },
        )
        raise
    except ValueError as error:
        services.audit.log_control_plane_event(
            event_type="v1_query_read",
            route_path=route_path,
            request_context=request_context,
            status_code=400,
            summary="Rejected invalid public room-scoped query.",
            metadata={
                "room_id": room_id,
                "query_kind": payload.query_kind,
                "limit": payload.limit,
                "offset": payload.offset,
                "result": "invalid_query",
                "detail": str(error),
            },
        )
        raise HTTPException(status_code=400, detail=str(error)) from error
