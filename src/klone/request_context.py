from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from fastapi import Request


REQUEST_ID_HEADER = "x-request-id"
TRACE_ID_HEADER = "x-trace-id"
PRINCIPAL_HEADER = "x-klone-principal"
ROLE_HEADER = "x-klone-role"


@dataclass(frozen=True)
class RequestContext:
    request_id: str
    trace_id: str
    principal: str
    actor_role: str

    def as_headers(self) -> dict[str, str]:
        return {
            "X-Request-Id": self.request_id,
            "X-Trace-Id": self.trace_id,
            "X-Klone-Principal": self.principal,
            "X-Klone-Role": self.actor_role,
        }


def _clean_header_value(value: str | None, *, fallback: str) -> str:
    if value is None:
        return fallback
    cleaned = " ".join(value.strip().split())
    return cleaned or fallback


def build_request_context(request: Request) -> RequestContext:
    request_token = uuid4().hex
    request_id = _clean_header_value(
        request.headers.get(REQUEST_ID_HEADER),
        fallback=f"req:{request_token}",
    )
    trace_id = _clean_header_value(
        request.headers.get(TRACE_ID_HEADER),
        fallback=f"trace:{request_token}",
    )
    principal = _clean_header_value(
        request.headers.get(PRINCIPAL_HEADER),
        fallback="owner",
    )
    actor_role = _clean_header_value(
        request.headers.get(ROLE_HEADER),
        fallback="owner",
    )
    return RequestContext(
        request_id=request_id,
        trace_id=trace_id,
        principal=principal,
        actor_role=actor_role,
    )

