"""Persistent SQLite integration for authorized bounded Memory Core read and audit."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from klone.cognition_memory import probe_memory
from klone.hypervisor_dispatch import DispatchDenied
from klone.hypervisor_runtime import HypervisorRuntime
from klone.hypervisor_safe_pipeline import SafeReadPipeline
from klone.repository import KloneRepository


class PersistentMemoryAuditIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "klone.sqlite"
        self.repo = KloneRepository(self.db_path)
        self.repo.initialize()

    def tearDown(self):
        self.tmp.cleanup()

    def make_pipeline(self, *, fail_audit=False):
        def audit(event, decision, seam):
            if fail_audit:
                raise OSError("durable audit unavailable")
            self.repo.record_audit_event(
                event_type="integration_" + event,
                actor="integration-test",
                target_type="service_seam",
                target_id=seam,
                room_id=decision.room_id,
                classification_level="public",
                summary="Bounded read integration audit",
                metadata={"trace_id": decision.trace_id},
            )

        return SafeReadPipeline(
            runtime=HypervisorRuntime(),
            handlers={"MemoryFacade": lambda room: probe_memory(
                self.repo, room_id=room, limit=5).public_summary()},
            audit=audit,
            authorize_output=lambda level: "allowed" if level == "public" else "denied",
        )

    def test_real_empty_memory_repository_and_durable_audit(self):
        result = self.make_pipeline().read(
            seam="MemoryFacade", room_id="public-room",
            actor_role="owner", trace_id="persistent-72",
            classification_level="public",
        )
        self.assertEqual(result.payload["room_id"], "public-room")
        self.assertEqual(result.payload["event_count"], 0)
        self.assertNotIn("evidence_text", result.payload)
        reopened = KloneRepository(self.db_path)
        rows = reopened.list_audit_events(room_id="public-room", limit=10)
        self.assertEqual({row["event_type"] for row in rows},
                         {"integration_delegated", "integration_completed"})
        self.assertEqual(len(rows), 2)
        self.assertTrue(all("persistent-72" in row["metadata_json"] for row in rows))

    def test_denied_classification_cannot_read_memory(self):
        with self.assertRaises(DispatchDenied):
            self.make_pipeline().read(
                seam="MemoryFacade", room_id="public-room",
                actor_role="owner", trace_id="denied-72",
                classification_level="restricted_bio",
            )
        self.assertEqual(self.repo.list_audit_events(room_id="public-room")[0]["event_type"],
                         "integration_denied")

    def test_audit_storage_failure_blocks_read(self):
        with self.assertRaisesRegex(OSError, "durable audit unavailable"):
            self.make_pipeline(fail_audit=True).read(
                seam="MemoryFacade", room_id="public-room",
                actor_role="owner", trace_id="fail-72",
                classification_level="public",
            )
        self.assertEqual(self.repo.list_audit_events(room_id="public-room"), [])


if __name__ == "__main__":
    unittest.main()
