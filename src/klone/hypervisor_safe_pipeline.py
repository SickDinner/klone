from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from .hypervisor_dispatch import DispatchDenied
from .hypervisor_runtime import HypervisorRuntime, RoutingDecision


@dataclass(frozen=True)
class SafeReadResult:
    trace_id: str
    room_id: str
    seam: str
    payload: Mapping[str, Any]


class SafeReadPipeline:
    """Fail-closed read-only pipeline with explicit audit and output authorization.

    This synchronous adapter does not claim to enforce execution timeouts.
    Handlers must themselves be bounded and return mappings.
    """

    def __init__(
        self,
        *,
        runtime: HypervisorRuntime,
        handlers: Mapping[str, Callable[[str], Mapping[str, Any]]],
        audit: Callable[[str, RoutingDecision, str], None],
        authorize_output: Callable[[str], str],
    ) -> None:
        if not callable(audit) or not callable(authorize_output):
            raise ValueError("Audit and output authorization callbacks are mandatory")
        if not handlers or any(not callable(handler) for handler in handlers.values()):
            raise ValueError("Explicit read handlers are required")
        self._runtime = runtime
        self._handlers = dict(handlers)
        self._audit = audit
        self._authorize_output = authorize_output

    def read(
        self,
        *,
        seam: str,
        room_id: str,
        actor_role: str,
        trace_id: str,
        classification_level: str,
    ) -> SafeReadResult:
        decision = self._runtime.plan(
            room_id=room_id, actor_role=actor_role, permission="read",
            trace_id=trace_id, classification_level=classification_level,
        )
        if decision.decision != "allowed":
            self._audit("denied", decision, seam)
            raise DispatchDenied(decision.reason)
        handler = self._handlers.get(seam)
        if handler is None:
            self._audit("denied", decision, seam)
            raise DispatchDenied("Unregistered service seam")
        # Output authorization must happen before fetching any protected data.
        output_decision = self._authorize_output(classification_level)
        if output_decision != "allowed":
            self._audit("denied", decision, seam)
            raise DispatchDenied("Output policy forbids raw read")
        # A failing audit prevents execution. No silent best-effort audit.
        self._audit("delegated", decision, seam)
        try:
            payload = handler(room_id)
            if not isinstance(payload, Mapping):
                raise TypeError("Read handler must return a mapping")
            # Restrict exposed result to JSON-compatible primitives and copies.
            import json
            safe_payload = json.loads(json.dumps(dict(payload), allow_nan=False))
            if not isinstance(safe_payload, dict):
                raise TypeError("Invalid handler result")
            # Recheck output policy before releasing data.
            if self._authorize_output(classification_level) != "allowed":
                raise DispatchDenied("Output policy changed during execution")
            self._audit("completed", decision, seam)
        except Exception:
            self._audit("failed", decision, seam)
            raise
        return SafeReadResult(trace_id, room_id, seam, safe_payload)
