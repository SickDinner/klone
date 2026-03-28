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
    return PublicCapabilitiesResponse(
        api_version="v1",
        request_context=RequestContextRecord(
            request_id=request_context.request_id,
            trace_id=request_context.trace_id,
            principal=request_context.principal,
            actor_role=request_context.actor_role,
        ),
        services=services.seam_descriptors(),
        module_registry=module_registry_payload(),
        capabilities=services.public_capabilities(),
        contracts=contract_registry_payload(),
    )
