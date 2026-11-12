"""Trusted in-process Mission Control gateway for public research previews.

This is NOT an HTTP endpoint. Hosting application must authenticate the actor,
protect the database and source inputs, and log security events. Only preview
is exposed: no persistence or approval side effects.
"""
from __future__ import annotations

from dataclasses import dataclass

from .hypervisor_runtime import HypervisorRuntime
from .integrated_research_operations import ResearchPreview, preview_public_research
from .research_source_manifest import PublicSourceManifest


@dataclass(frozen=True)
class ResearchGatewayDecision:
    room_id: str
    trace_id: str
    permission: str
    decision: str
    reason: str


def preview_via_mission_control(
    *, runtime: HypervisorRuntime, actor_role: str, trace_id: str,
    authenticate_actor, json_text: str,
    manifests: dict[str, PublicSourceManifest], source_bytes: dict[str, bytes],
) -> tuple[ResearchGatewayDecision, ResearchPreview]:
    if not isinstance(runtime, HypervisorRuntime) or not callable(authenticate_actor):
        raise PermissionError("Trusted Mission Control runtime required")
    if not isinstance(trace_id, str) or not trace_id.strip() or len(trace_id) > 128:
        raise PermissionError("Valid trace required")
    if not authenticate_actor(actor_role):
        raise PermissionError("Actor authentication failed")
    route = runtime.plan(
        room_id="public-room", actor_role=actor_role,
        permission="read", trace_id=trace_id,
        classification_level="public")
    if route.decision != "allowed":
        raise PermissionError("Hypervisor denied public research preview")
    preview = preview_public_research(
        json_text=json_text, manifests=manifests, source_bytes=source_bytes)
    return ResearchGatewayDecision(
        route.room_id, trace_id, route.permission, route.decision,
        route.reason), preview
