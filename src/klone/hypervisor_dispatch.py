from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Any

from .hypervisor_runtime import HypervisorRuntime, RoutingDecision


@dataclass(frozen=True)
class DispatchResult:
    route: RoutingDecision
    seam: str
    result: Any


class DispatchDenied(PermissionError):
    pass


class HypervisorDispatcher:
    """Explicit, read-only delegation. Audit callbacks must persist before work."""

    def __init__(
        self,
        *,
        runtime: HypervisorRuntime,
        handlers: Mapping[str, Callable[[str], Any]],
        audit: Callable[[str, RoutingDecision, str], None],
    ) -> None:
        if not callable(audit):
            raise ValueError("A durable audit callback is required")
        self._runtime = runtime
        self._handlers = dict(handlers)
        if not self._handlers or any(not callable(handler) for handler in self._handlers.values()):
            raise ValueError("Explicit callable handlers are required")
        self._audit = audit

    def dispatch_read(
        self,
        *,
        seam: str,
        room_id: str,
        actor_role: str,
        trace_id: str,
        classification_level: str,
    ) -> DispatchResult:
        route = self._runtime.plan(
            room_id=room_id,
            actor_role=actor_role,
            permission="read",
            trace_id=trace_id,
            classification_level=classification_level,
        )
        if route.decision != "allowed":
            self._audit("denied", route, seam)
            raise DispatchDenied(route.reason)
        handler = self._handlers.get(seam)
        if handler is None:
            self._audit("denied", route, seam)
            raise DispatchDenied("Unregistered service seam")
        # Audit must succeed before any handler is invoked.
        self._audit("delegated", route, seam)
        try:
            result = handler(room_id)
        except Exception:
            self._audit("failed", route, seam)
            raise
        self._audit("completed", route, seam)
        return DispatchResult(route=route, seam=seam, result=result)
