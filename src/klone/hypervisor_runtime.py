from __future__ import annotations

from dataclasses import dataclass

from .guards import access_guard, classification_guard
from .rooms import room_registry


@dataclass(frozen=True)
class RoutingDecision:
    room_id: str
    actor_role: str
    permission: str
    decision: str
    reason: str
    supervisor: str | None
    classification: str | None
    trace_id: str


class HypervisorRuntime:
    """Deterministic, side-effect-free policy gate. Does not execute work."""

    def plan(
        self,
        *,
        room_id: str,
        actor_role: str,
        permission: str,
        trace_id: str,
        classification_level: str | None = None,
    ) -> RoutingDecision:
        if not trace_id.strip():
            raise ValueError("trace_id is required")
        room = room_registry.get_room(room_id)
        if room is None:
            return RoutingDecision(room_id, actor_role, permission, "blocked",
                                   "Unknown room", None, None, trace_id)
        access = access_guard.evaluate(
            room_id=room_id, actor_role=actor_role, requested_permission=permission
        )
        if access.decision != "allowed":
            return RoutingDecision(room_id, actor_role, permission, access.decision,
                                   access.reason, None, room.classification, trace_id)
        if classification_level is not None:
            if classification_level not in {"public", "personal", "intimate", "restricted_bio"}:
                return RoutingDecision(room_id, actor_role, permission, "blocked",
                                       "Unknown classification", None, room.classification, trace_id)
            classification = classification_guard.evaluate(
                classification_level=classification_level, room_id=room_id
            )
            if classification.decision != "allowed":
                return RoutingDecision(room_id, actor_role, permission, "blocked",
                                       classification.reason, None, room.classification, trace_id)
        if not room.supervisor.strip():
            return RoutingDecision(room_id, actor_role, permission, "blocked",
                                   "Missing supervisor", None, room.classification, trace_id)
        return RoutingDecision(room_id, actor_role, permission, "allowed",
                               "Routing permitted; no task executed", room.supervisor,
                               room.classification, trace_id)
