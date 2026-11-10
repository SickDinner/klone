from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from .hypervisor_runtime import HypervisorRuntime
from .hypervisor_safe_pipeline import SafeReadPipeline, SafeReadResult
from .hypervisor_worker import BoundedWorkerRunner


class GovernedWorkerReads:
    """Explicit composition seam: policy, audit, output gate, then worker.

    No worker command, argv or classification is accepted from a request.
    The worker registry is fixed at construction time. This is not a public API.
    """

    def __init__(
        self,
        *,
        runner: BoundedWorkerRunner,
        seams: Mapping[str, str],
        audit: Callable[..., None],
        authorize_output: Callable[[str], str],
        max_output_bytes: int = 65536,
    ) -> None:
        if not seams or any(not seam or not worker for seam, worker in seams.items()):
            raise ValueError("Explicit seam-to-worker mapping required")
        handlers: dict[str, Callable[[str], Mapping[str, Any]]] = {}
        for seam, worker in seams.items():
            def invoke(room_id: str, *, _worker: str = worker) -> Mapping[str, Any]:
                # Workers receive no room contents or arbitrary arguments.
                # Room identity is only passed to policy/audit layers.
                return runner.run(_worker).payload
            handlers[seam] = invoke
        self._pipeline = SafeReadPipeline(
            runtime=HypervisorRuntime(), handlers=handlers,
            audit=audit, authorize_output=authorize_output,
            max_output_bytes=max_output_bytes,
        )

    def read(
        self, *, seam: str, room_id: str, actor_role: str,
        trace_id: str, classification_level: str,
    ) -> SafeReadResult:
        return self._pipeline.read(
            seam=seam, room_id=room_id, actor_role=actor_role,
            trace_id=trace_id, classification_level=classification_level,
        )
