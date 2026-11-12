"""Bounded integration test: cognition -> Hypervisor -> audited memory-shaped read -> evidence.

This test uses an in-memory, synthetic memory facade. It does NOT assert
integration with KLONE's persistent Memory Core or production audit storage.
"""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from klone.cognition_core import CognitionCore
from klone.hypervisor_dispatch import DispatchDenied
from klone.hypervisor_runtime import HypervisorRuntime
from klone.hypervisor_safe_pipeline import SafeReadPipeline
from klone.test_evidence_ledger import EvidenceLedger
from klone.test_evidence_dashboard import summarize


class CognitionControlPlaneEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = EvidenceLedger(Path(self.temp.name) / "evidence.sqlite")
        self.db.initialize()
        self.sha = "a" * 40

    def tearDown(self):
        self.temp.cleanup()

    def test_authorized_cognition_read_audit_replay_and_evidence(self):
        cognition = CognitionCore(memory_capacity=16)
        cognition.run(8)
        self.assertEqual(cognition.snapshot(), cognition.replay().snapshot())
        events = []
        reads = []

        def facade(room):
            reads.append(room)
            return {"room": room, "steps": cognition.snapshot()["step"],
                    "trace_digest": cognition.trace_digest()}

        pipeline = SafeReadPipeline(
            runtime=HypervisorRuntime(),
            handlers={"MemoryFacade": facade},
            audit=lambda event, route, seam: events.append((event, route.trace_id, seam)),
            authorize_output=lambda classification: "allowed" if classification == "public" else "denied",
        )
        result = pipeline.read(
            seam="MemoryFacade", room_id="public-room", actor_role="owner",
            trace_id="integration-72", classification_level="public",
        )
        self.assertEqual(result.payload["steps"], 8)
        self.assertEqual(result.payload["trace_digest"], cognition.trace_digest())
        self.assertEqual(reads, ["public-room"])
        self.assertEqual([event[0] for event in events], ["delegated", "completed"])
        _, inserted = self.db.append({
            "source": "github_actions", "run_id": "integration-72",
            "commit": self.sha, "status": "success",
            "observed_at": "2026-11-12T16:00:00Z",
            "environment": "synthetic-integration",
            "details": {"trace_digest": cognition.trace_digest(), "steps": 8},
        })
        self.assertTrue(inserted)
        self.assertEqual(summarize(self.db, self.sha)["sources"]["github_actions"]["success"], 1)
        self.assertEqual(summarize(self.db, self.sha)["review_state"], "pending_evidence")

    def test_denied_access_never_reaches_memory_facade(self):
        reads = []
        events = []
        pipeline = SafeReadPipeline(
            runtime=HypervisorRuntime(),
            handlers={"MemoryFacade": lambda room: reads.append(room) or {"items": []}},
            audit=lambda event, route, seam: events.append(event),
            authorize_output=lambda _: "allowed",
        )
        with self.assertRaises(DispatchDenied):
            pipeline.read(seam="MemoryFacade", room_id="public-room",
                          actor_role="owner", trace_id="denied-72",
                          classification_level="restricted_bio")
        self.assertEqual(reads, [])
        self.assertEqual(events, ["denied"])

    def test_failed_prehandler_audit_prevents_memory_read_and_evidence(self):
        reads = []
        pipeline = SafeReadPipeline(
            runtime=HypervisorRuntime(),
            handlers={"MemoryFacade": lambda room: reads.append(room) or {"items": []}},
            audit=lambda *_: (_ for _ in ()).throw(OSError("audit unavailable")),
            authorize_output=lambda _: "allowed",
        )
        with self.assertRaises(OSError):
            pipeline.read(seam="MemoryFacade", room_id="public-room",
                          actor_role="owner", trace_id="audit-72",
                          classification_level="public")
        self.assertEqual(reads, [])
        self.assertEqual(self.db.list_for_commit(self.sha), [])


if __name__ == "__main__":
    unittest.main()
