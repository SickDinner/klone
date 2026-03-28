from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from .request_context import RequestContext
from .schemas import PublicCapabilitiesResponse, RequestContextRecord
from .services import ServiceContainer, module_registry_payload
from .v1_contracts import contract_registry_payload


router = APIRouter(prefix="/v1")


def get_service_container(request: Request) -> ServiceContainer:
    return request.app.state.services


def get_request_context(request: Request) -> RequestContext:
    return request.state.request_context


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
