from __future__ import annotations

import unittest

from klone.hypervisor_dispatch import DispatchDenied
from klone.hypervisor_worker_integration import GovernedWorkerReads


class FakeRunner:
    def __init__(self):
        self.calls = []

    def run(self, worker):
        self.calls.append(worker)
        return type("Result", (), {"payload": {"ok": True}})()


class GovernedWorkerTests(unittest.TestCase):
    def setUp(self):
        self.runner = FakeRunner()
        self.events = []
        self.service = GovernedWorkerReads(
            runner=self.runner,
            seams={"worker.read": "fixed-worker"},
            audit=lambda event, route, seam: self.events.append((event, route.trace_id)),
            authorize_output=lambda level: "allowed" if level == "public" else "blocked",
        )

    def read(self, **overrides):
        params = dict(seam="worker.read", room_id="public-room",
                      actor_role="owner", trace_id="trace-worker",
                      classification_level="public")
        params.update(overrides)
        return self.service.read(**params)

    def test_allowed_read_audited(self):
        self.assertEqual(self.read().payload, {"ok": True})
        self.assertEqual(self.runner.calls, ["fixed-worker"])
        self.assertEqual([event for event, _ in self.events], ["delegated", "completed"])

    def test_unregistered_seam_never_runs(self):
        with self.assertRaises(DispatchDenied):
            self.read(seam="unregistered")
        self.assertEqual(self.runner.calls, [])

    def test_wrong_classification_never_runs(self):
        with self.assertRaises(DispatchDenied):
            self.read(classification_level="intimate")
        self.assertEqual(self.runner.calls, [])

    def test_unknown_room_never_runs(self):
        with self.assertRaises(DispatchDenied):
            self.read(room_id="nonexistent-room")
        self.assertEqual(self.runner.calls, [])

    def test_repeated_unknown_room_attempts_never_execute_worker(self):
        for attempt in range(3):
            with self.subTest(attempt=attempt):
                with self.assertRaises(DispatchDenied):
                    self.read(room_id="nonexistent-room")
        self.assertEqual(self.runner.calls, [])

    def test_preexecution_audit_error_never_executes_worker(self):
        attempts = []

        def broken_audit(event, route, seam):
            attempts.append(event)
            raise OSError("synthetic audit persistence error")

        service = GovernedWorkerReads(
            runner=self.runner,
            seams={"worker.read": "fixed-worker"},
            audit=broken_audit,
            authorize_output=lambda _: "allowed",
        )
        with self.assertRaisesRegex(OSError, "synthetic audit persistence error"):
            service.read(
                seam="worker.read", room_id="public-room", actor_role="owner",
                trace_id="trace-audit-failure", classification_level="public",
            )
        self.assertEqual(self.runner.calls, [])
        self.assertEqual(attempts, ["delegated"])

    def test_audit_failure_never_runs(self):
        service = GovernedWorkerReads(
            runner=self.runner,
            seams={"worker.read": "fixed-worker"},
            audit=lambda *args: (_ for _ in ()).throw(OSError("audit unavailable")),
            authorize_output=lambda _: "allowed",
        )
        with self.assertRaises(OSError):
            service.read(seam="worker.read", room_id="public-room",
                         actor_role="owner", trace_id="trace-fail",
                         classification_level="public")
        self.assertEqual(self.runner.calls, [])


if __name__ == "__main__":
    unittest.main()
