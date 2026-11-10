from __future__ import annotations

from dataclasses import dataclass
import json
import subprocess
from typing import Mapping, Sequence


@dataclass(frozen=True)
class WorkerResult:
    worker: str
    payload: dict[str, object]


class WorkerExecutionError(RuntimeError):
    pass


class BoundedWorkerRunner:
    """Run only preconfigured workers in a child process, never through a shell.

    A timeout kills the child process, not necessarily its descendants.
    This is not a security sandbox or OS resource isolation boundary.
    """

    def __init__(
        self,
        *,
        workers: Mapping[str, Sequence[str]],
        timeout_seconds: float = 5.0,
        max_output_bytes: int = 65536,
    ) -> None:
        if timeout_seconds <= 0 or max_output_bytes < 1:
            raise ValueError("Positive timeout and output limit required")
        if not workers or any(
            not name or not argv or any(not isinstance(x, str) or not x for x in argv)
            for name, argv in workers.items()
        ):
            raise ValueError("Workers must have fixed nonempty argument vectors")
        self._workers = {name: tuple(argv) for name, argv in workers.items()}
        self._timeout = timeout_seconds
        self._limit = max_output_bytes

    def run(self, worker: str) -> WorkerResult:
        argv = self._workers.get(worker)
        if argv is None:
            raise WorkerExecutionError("Unregistered worker")
        try:
            completed = subprocess.run(
                argv,
                shell=False,
                capture_output=True,
                timeout=self._timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise WorkerExecutionError("Worker timed out") from exc
        except OSError as exc:
            raise WorkerExecutionError("Worker launch failed") from exc
        if completed.returncode != 0:
            raise WorkerExecutionError("Worker failed")
        if len(completed.stdout) > self._limit:
            raise WorkerExecutionError("Worker output exceeds byte limit")
        try:
            payload = json.loads(completed.stdout)
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise WorkerExecutionError("Worker returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise WorkerExecutionError("Worker must return a JSON object")
        return WorkerResult(worker=worker, payload=payload)
