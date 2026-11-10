from __future__ import annotations

import unittest

from klone.hypervisor_dispatch import DispatchDenied, HypervisorDispatcher
from klone.hypervisor_runtime import HypervisorRuntime


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.calls = []
        self.dispatcher = HypervisorDispatcher(
            runtime=HypervisorRuntime(),
            handlers={"MemoryFacade": lambda room: self.calls.append(room) or {"count": 0}},
            audit=lambda event, route, seam: self.events.append((event, route.trace_id, seam)),
        )

    def dispatch(self, **overrides):
        args = dict(seam="MemoryFacade", room_id="public-room",
                    actor_role="owner", trace_id="trace-10",
                    classification_level="public")
        args.update(overrides)
        return self.dispatcher.dispatch_read(**args)

    def test_delegates_and_audits(self):
        result = self.dispatch()
        self.assertEqual(result.result, {"count": 0})
        self.assertEqual(self.calls, ["public-room"])
        self.assertEqual([e[0] for e in self.events], ["delegated", "completed"])

    def test_cross_classification_is_denied(self):
        with self.assertRaises(DispatchDenied):
            self.dispatch(classification_level="intimate")
        self.assertFalse(self.calls)
        self.assertEqual(self.events[0][0], "denied")

    def test_unknown_seam_is_denied(self):
        with self.assertRaises(DispatchDenied):
            self.dispatch(seam="Unregistered")
        self.assertFalse(self.calls)

    def test_role_is_denied(self):
        with self.assertRaises(DispatchDenied):
            self.dispatch(actor_role="worker")
        self.assertFalse(self.calls)

    def test_audit_failure_prevents_delegation(self):
        dispatcher = HypervisorDispatcher(
            runtime=HypervisorRuntime(),
            handlers={"MemoryFacade": lambda room: self.calls.append(room)},
            audit=lambda event, route, seam: (_ for _ in ()).throw(OSError("audit unavailable")),
        )
        with self.assertRaises(OSError):
            dispatcher.dispatch_read(seam="MemoryFacade", room_id="public-room",
                                     actor_role="owner", trace_id="trace-11",
                                     classification_level="public")
        self.assertFalse(self.calls)


if __name__ == "__main__":
    unittest.main()
