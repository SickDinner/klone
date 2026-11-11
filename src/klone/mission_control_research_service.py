"""Trusted-host Mission Control adapter for curated public research.

Not a network endpoint or authentication implementation. The host must supply
authenticated principal/role, path authorization, and durable audit callbacks.
No automatic claim approval or publication is performed.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .hypervisor_runtime import HypervisorRuntime
from .integrated_research_core import IntegratedResearchResult, run_integrated_public_research
from .integrated_research_operations import (
    ResearchPreview, ResearchInspection, preview_public_research,
    inspect_public_research,
)
from .research_source_manifest import PublicSourceManifest


@dataclass(frozen=True)
class ResearchServiceRequest:
    principal: str
    actor_role: str
    trace_id: str
    dossier_id: str


class MissionControlResearchService:
    """Synchronous adapter. Callback trust belongs to the hosting service."""

    def __init__(
        self, *, database_path: Path,
        authenticate: Callable[[str, str], bool],
        authorize: Callable[[str, str, str], bool],
        audit: Callable[[str, ResearchServiceRequest, str], None],
        runtime: HypervisorRuntime,
    ):
        if (not callable(authenticate) or not callable(authorize)
                or not callable(audit) or not isinstance(runtime, HypervisorRuntime)):
            raise PermissionError("Trusted service dependencies required")
        self.database_path = Path(database_path)
        self.authenticate = authenticate
        self.authorize = authorize
        self.audit = audit
        self.runtime = runtime

    def _gate(self, request: ResearchServiceRequest, action: str) -> None:
        if (not isinstance(request, ResearchServiceRequest)
                or not isinstance(request.principal, str)
                or not request.principal.strip()
                or not isinstance(request.actor_role, str)
                or not request.actor_role.strip()
                or not isinstance(request.trace_id, str)
                or not request.trace_id.strip()
                or not isinstance(request.dossier_id, str)
                or not 1 <= len(request.dossier_id) <= 128
                or not request.dossier_id.strip()):
            raise PermissionError("Invalid research request")
        if self.authenticate(request.principal, request.actor_role) is not True:
            raise PermissionError("Research identity denied")
        decision = self.runtime.plan(
            room_id="public-room", actor_role=request.actor_role,
            permission="read" if action == "inspect" else "propose",
            trace_id=request.trace_id, classification_level="public")
        if decision.decision != "allowed":
            raise PermissionError("Hypervisor denied research operation")
        if self.authorize(request.principal, request.dossier_id, action) is not True:
            raise PermissionError("Research operation authorization denied")
        # A failed admission audit prevents the operation.
        self.audit("admitted", request, action)

    def preview(
        self, *, request: ResearchServiceRequest, json_text: str,
        manifests: dict[str, PublicSourceManifest], source_bytes: dict[str, bytes],
    ) -> ResearchPreview:
        self._gate(request, "preview")
        try:
            result = preview_public_research(
                json_text=json_text, manifests=manifests, source_bytes=source_bytes)
        except Exception:
            self.audit("failed", request, "preview")
            raise
        self.audit("completed", request, "preview")
        return result

    def run(
        self, *, request: ResearchServiceRequest, json_text: str,
        manifests: dict[str, PublicSourceManifest], source_bytes: dict[str, bytes],
    ) -> IntegratedResearchResult:
        self._gate(request, "run")
        try:
            result = run_integrated_public_research(
                database_path=self.database_path, dossier_id=request.dossier_id,
                json_text=json_text, manifests=manifests, source_bytes=source_bytes)
        except Exception:
            self.audit("failed", request, "run")
            raise
        # Completion audit is not atomic with dossier persistence.
        self.audit("completed", request, "run")
        return result

    def inspect(
        self, *, request: ResearchServiceRequest, version: int,
    ) -> ResearchInspection:
        self._gate(request, "inspect")
        try:
            result = inspect_public_research(
                database_path=self.database_path,
                dossier_id=request.dossier_id, version=version)
        except Exception:
            self.audit("failed", request, "inspect")
            raise
        self.audit("completed", request, "inspect")
        return result
