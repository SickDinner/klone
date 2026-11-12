from __future__ import annotations

import unittest

from klone.hypervisor_audit_adapter import DurableHypervisorAudit, authorize_hypervisor_raw_output
from klone.hypervisor_runtime import RoutingDecision


class FakeAudit:
    def __init__(self):
        self.calls = []

    def log_event(self, **kwargs):
        self.calls.append(kwargs)


class HypervisorAuditAdapterTests(unittest.TestCase):
    def setUp(self):
        self.service = FakeAudit()
        self.adapter = DurableHypervisorAudit(self.service)
        self.route = RoutingDecision(
            room_id="public-room", actor_role="owner", permission="read",
            decision="allowed", reason="ok", supervisor="hypervisor",
            classification="public", trace_id="trace-42",
        )

    def test_audit_event_contains_trace_without_payload(self):
        self.adapter("delegated", self.route, "MemoryFacade")
        record = self.service.calls[0]
        self.assertEqual(record["event_type"], "hypervisor_delegated")
        self.assertEqual(record["metadata"]["trace_id"], "trace-42")
        self.assertNotIn("payload", record["metadata"])

    def test_unknown_room_classification_cannot_be_downgraded(self):
        route = RoutingDecision("unknown", "owner", "read", "blocked", "unknown",
                                None, None, "trace-43")
        with self.assertRaises(ValueError):
            self.adapter("denied", route, "MemoryFacade")
        self.assertEqual(self.service.calls, [])

    def test_unrecognized_audit_event_rejected(self):
        with self.assertRaises(ValueError):
            self.adapter("surprise", self.route, "MemoryFacade")

    def test_unrecognized_event_does_not_write_audit_record(self):
        with self.assertRaises(ValueError):
            self.adapter("unexpected_event", self.route, "MemoryFacade")
        self.assertEqual(self.service.calls, [])

    def test_audit_records_do_not_include_raw_route_payload(self):
        self.adapter("delegated", self.route, "MemoryFacade")
        record = self.service.calls[0]
        self.assertNotIn("payload", record)
        self.assertNotIn("evidence_text", record["metadata"])
        self.assertNotIn("raw_content", record["metadata"])

    def test_public_output_policy_allowed(self):
        self.assertEqual(authorize_hypervisor_raw_output("public"), "allowed")

    def test_unknown_classification_blocked(self):
        self.assertEqual(authorize_hypervisor_raw_output("invalid"), "blocked")


if __name__ == "__main__":
    unittest.main()
