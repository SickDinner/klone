from __future__ import annotations

from collections.abc import Mapping
import json
import sqlite3
from typing import Any

from .contracts import ClassificationLevel
from .guards import audit_guard
from .repository import KloneRepository
from .request_context import RequestContext
from .schemas import AuditEventRecord, ControlPlaneAuditRecord


class AuditService:
    def __init__(self, repository: KloneRepository) -> None:
        self.repository = repository

    def log_event(
        self,
        *,
        event_type: str,
        actor: str,
        target_type: str,
        target_id: str | None,
        room_id: str | None,
        classification_level: ClassificationLevel,
        summary: str,
        metadata: Mapping[str, Any] | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> AuditEventRecord:
        decision = audit_guard.evaluate(
            event_type=event_type,
            actor=actor,
            target_type=target_type,
            summary=summary,
            metadata=metadata,
        )
        if decision.decision != "allowed":
            raise ValueError(decision.reason)
        payload = self.repository.record_audit_event(
            event_type=event_type,
            actor=actor,
            target_type=target_type,
            target_id=target_id,
            room_id=room_id,
            classification_level=classification_level,
            summary=summary,
            metadata=metadata,
            conn=conn,
        )
        metadata_json = payload.pop("metadata_json", None)
        if metadata_json:
            payload["metadata"] = json.loads(metadata_json)
        return AuditEventRecord.model_validate(payload)

    def log_control_plane_event(
        self,
        *,
        event_type: str,
        route_path: str,
        request_context: RequestContext,
        status_code: int,
        summary: str,
        metadata: Mapping[str, Any] | None = None,
        conn: sqlite3.Connection | None = None,
    ) -> ControlPlaneAuditRecord:
        decision = audit_guard.evaluate(
            event_type=event_type,
            actor=request_context.principal,
            target_type="control_plane_route",
            summary=summary,
            metadata=metadata,
        )
        if decision.decision != "allowed":
            raise ValueError(decision.reason)
        payload = self.repository.record_control_plane_audit_event(
            event_type=event_type,
            route_path=route_path,
            actor=request_context.principal,
            actor_role=request_context.actor_role,
            principal=request_context.principal,
            request_id=request_context.request_id,
            trace_id=request_context.trace_id,
            status_code=status_code,
            summary=summary,
            metadata=metadata,
            conn=conn,
        )
        metadata_json = payload.pop("metadata_json", None)
        if metadata_json:
            payload["metadata"] = json.loads(metadata_json)
        return ControlPlaneAuditRecord.model_validate(payload)
