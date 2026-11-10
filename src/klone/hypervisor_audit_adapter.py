from __future__ import annotations

from .audit import AuditService
from .guards import output_guard
from .hypervisor_runtime import RoutingDecision


class DurableHypervisorAudit:
    """Adapter to KLONE's existing SQLite-backed audit service.

    No raw handler payload or private request data is written into metadata.
    AuditService.log_event raises on persistence errors; callers must fail closed.
    """

    def __init__(self, service: AuditService) -> None:
        self._service = service

    def __call__(self, event: str, route: RoutingDecision, seam: str) -> None:
        if event not in {"denied", "delegated", "completed", "failed"}:
            raise ValueError("Unknown hypervisor audit event")
        if route.classification is None:
            # Unknown room has no trustworthy classification to persist.
            # Never substitute public classification for an unknown room.
            raise ValueError("Cannot persist audit without room classification")
        self._service.log_event(
            event_type=f"hypervisor_{event}",
            actor=route.actor_role,
            target_type="service_seam",
            target_id=seam,
            room_id=route.room_id,
            classification_level=route.classification,
            summary=f"Hypervisor {event} service seam request.",
            metadata={
                "trace_id": route.trace_id,
                "permission": route.permission,
                "decision": route.decision,
                "supervisor": route.supervisor,
            },
        )


def authorize_hypervisor_raw_output(classification_level: str) -> str:
    """Bridge to KLONE OutputGuard; non-allowed states are never promoted."""
    if classification_level not in {"public", "personal", "intimate", "restricted_bio"}:
        return "blocked"
    return output_guard.evaluate(classification_level=classification_level).decision
