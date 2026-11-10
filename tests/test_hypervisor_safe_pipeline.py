from __future__ import annotations

import unittest

from klone.hypervisor_dispatch import DispatchDenied
from klone.hypervisor_runtime import HypervisorRuntime
from klone.hypervisor_safe_pipeline import SafeReadPipeline


class SafeReadPipelineTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.calls = []
        self.pipeline = SafeReadPipeline(
            runtime=HypervisorRuntime(),
            handlers={"MemoryFacade": lambda room: self.calls.append(room) or {"items": []}},
            audit=lambda event, route, seam: self.events.append(event),
            authorize_output=lambda classification: "allowed" if classification == "public" else "summary_only",
        )

    def run_read(self, **changes):
        args = dict(seam="MemoryFacade", room_id="public-room", actor_role="owner",
                    trace_id="trace-safe", classification_level="public")
        args.update(changes)
        return self.pipeline.read(**args)

    def test_success_returns_traceable_copy(self):
        result = self.run_read()
        self.assertEqual(result.trace_id, "trace-safe")
        self.assertEqual(result.payload, {"items": []})
        self.assertEqual(self.events, ["delegated", "completed"])

    def test_classification_mismatch_never_calls_handler(self):
        with self.assertRaises(DispatchDenied):
            self.run_read(classification_level="intimate")
        self.assertEqual(self.calls, [])

    def test_missing_seam_fails_closed(self):
        with self.assertRaises(DispatchDenied):
            self.run_read(seam="missing")
        self.assertEqual(self.calls, [])

    def test_output_policy_blocks_before_handler(self):
        with self.assertRaises(DispatchDenied):
            self.run_read(room_id="restricted-room", classification_level="personal")
        self.assertEqual(self.calls, [])

    def test_audit_failure_blocks_handler(self):
        pipeline = SafeReadPipeline(
            runtime=HypervisorRuntime(),
            handlers={"MemoryFacade": lambda room: self.calls.append(room)},
            audit=lambda *args: (_ for _ in ()).throw(OSError("storage unavailable")),
            authorize_output=lambda _: "allowed",
        )
        with self.assertRaises(OSError):
            pipeline.read(seam="MemoryFacade", room_id="public-room", actor_role="owner",
                          trace_id="trace-audit", classification_level="public")
        self.assertEqual(self.calls, [])

    def test_nonserializable_payload_fails_and_audits(self):
        pipeline = SafeReadPipeline(
            runtime=HypervisorRuntime(),
            handlers={"MemoryFacade": lambda room: {"bad": object()}},
            audit=lambda event, route, seam: self.events.append(event),
            authorize_output=lambda _: "allowed",
        )
        with self.assertRaises(TypeError):
            pipeline.read(seam="MemoryFacade", room_id="public-room", actor_role="owner",
                          trace_id="trace-bad", classification_level="public")
        self.assertEqual(self.events, ["delegated", "failed"])


if __name__ == "__main__":
    unittest.main()
