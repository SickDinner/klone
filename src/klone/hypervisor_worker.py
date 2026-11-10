from __future__ import annotations

from dataclasses import dataclass
import json
import subprocess
import os
import signal
import selectors
import time
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
        if os.name != "posix":
            raise WorkerExecutionError("Bounded workers require POSIX; Windows is disabled until Job Object isolation is implemented")
        argv = self._workers.get(worker)
        if argv is None:
            raise WorkerExecutionError("Unregistered worker")
        # Start a new process group on POSIX so timeout can terminate descendants.
        # Windows uses process termination; descendants need a Job Object for full isolation.
        kwargs = {"start_new_session": True} if os.name == "posix" else {}
        try:
            process = subprocess.Popen(
                argv, shell=False, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, **kwargs
            )
        except OSError as exc:
            raise WorkerExecutionError("Worker launch failed") from exc

        def terminate() -> None:
            if os.name == "posix":
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            elif process.poll() is None:
                process.kill()
            process.wait()

        output = bytearray()
        deadline = time.monotonic() + self._timeout
        try:
            if os.name == "posix":
                with selectors.DefaultSelector() as selector:
                    selector.register(process.stdout, selectors.EVENT_READ)
                    while True:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise WorkerExecutionError("Worker timed out")
                        events = selector.select(min(remaining, 0.1))
                        if events:
                            chunk = os.read(process.stdout.fileno(), min(8192, self._limit + 1 - len(output)))
                            if not chunk:
                                break
                            output.extend(chunk)
                            if len(output) > self._limit:
                                raise WorkerExecutionError("Worker output exceeds byte limit")
                        elif process.poll() is not None:
                            # Keep reading until EOF after exit.
                            continue
            else:
                # Windows pipe reads require a separate bounded implementation.
                raise WorkerExecutionError("Windows bounded pipe reader not yet implemented")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise WorkerExecutionError("Worker timed out")
            try:
                returncode = process.wait(timeout=remaining)
            except subprocess.TimeoutExpired as exc:
                raise WorkerExecutionError("Worker timed out") from exc
            if returncode != 0:
                raise WorkerExecutionError("Worker failed")
        except BaseException:
            terminate()
            raise
        finally:
            if process.stdout:
                process.stdout.close()
        try:
            payload = json.loads(output)
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise WorkerExecutionError("Worker returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise WorkerExecutionError("Worker must return a JSON object")
        return WorkerResult(worker=worker, payload=payload)
