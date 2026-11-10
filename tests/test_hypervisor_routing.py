from __future__ import annotations

import unittest

from klone.hypervisor_runtime import HypervisorRuntime


class HypervisorRoutingTests(unittest.TestCase):
    def setUp(self):
        self.runtime = HypervisorRuntime()

    def test_known_room_read_is_routable(self):
        decision = self.runtime.plan(
            room_id="public-room", actor_role="owner", permission="read",
            classification_level="public", trace_id="trace-1"
        )
        self.assertEqual(decision.decision, "allowed")
        self.assertEqual(decision.supervisor, "hypervisor")
        self.assertEqual(decision.trace_id, "trace-1")

    def test_unknown_room_fails_closed(self):
        decision = self.runtime.plan(
            room_id="not-a-room", actor_role="owner", permission="read", trace_id="trace-2"
        )
        self.assertEqual(decision.decision, "blocked")
        self.assertIsNone(decision.supervisor)

    def test_role_cannot_escalate(self):
        decision = self.runtime.plan(
            room_id="restricted-room", actor_role="evaluator",
            permission="read", trace_id="trace-3"
        )
        self.assertEqual(decision.decision, "blocked")
        self.assertIsNone(decision.supervisor)

    def test_approval_does_not_delegate(self):
        decision = self.runtime.plan(
            room_id="public-room", actor_role="owner",
            permission="write", trace_id="trace-4"
        )
        self.assertEqual(decision.decision, "requires_approval")
        self.assertIsNone(decision.supervisor)

    def test_classification_mismatch_fails_closed(self):
        decision = self.runtime.plan(
            room_id="public-room", actor_role="owner", permission="read",
            classification_level="intimate", trace_id="trace-5"
        )
        self.assertEqual(decision.decision, "blocked")
        self.assertIsNone(decision.supervisor)

    def test_missing_trace_rejected(self):
        with self.assertRaises(ValueError):
            self.runtime.plan(
                room_id="public-room", actor_role="owner",
                permission="read", trace_id=""
            )


if __name__ == "__main__":
    unittest.main()
