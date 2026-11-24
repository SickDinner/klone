"""KLONE v3.0 cross-domain pulse remains read-only and never authorizes."""
import unittest
from klone.acceptance_matrix import DOMAINS
from klone.memory_continuity_v30 import PublicMemoryEvent
from klone.system_readiness_v30 import build_system_review_pulse

T = "2026-11-24T08:00:00Z"

def event(i):
    return PublicMemoryEvent(event_id=i, recorded_at=T, occurred_at=T)


def pulse(states=None, before=None, after=None):
    return build_system_review_pulse(domain_states=states or dict.fromkeys(DOMAINS, "passed"),
                                     memory_before=before or [event(1)],
                                     memory_after=after or [event(1)])


class SystemPulseV30Tests(unittest.TestCase):
    def test_all_passed_still_not_deployment_approval(self):
        report = pulse()
        self.assertEqual(report["review_status"], "manual_review_only")
        self.assertFalse(report["permission_granted"])
        self.assertFalse(report["production_readiness_verified"])
        self.assertFalse(report["deployment_approval"])
        self.assertIn("external_provenance_unverified", report["blocking_review_reasons"])

    def test_all_12_domains_required(self):
        with self.assertRaises(ValueError):
            pulse({"memory": "passed"})

    def test_failed_hypervisor_reported(self):
        states = dict.fromkeys(DOMAINS, "passed")
        states["hypervisor"] = "failed"
        self.assertIn("domain:hypervisor", pulse(states)["blocking_review_reasons"])

    def test_nonapplicable_is_not_passed(self):
        states = dict.fromkeys(DOMAINS, "passed")
        states["genomics"] = "not_applicable"
        self.assertIn("domain:genomics", pulse(states)["blocking_review_reasons"])

    def test_unknown_field_denied(self):
        states = dict.fromkeys(DOMAINS, "passed")
        states["new_autonomy_layer"] = "passed"
        with self.assertRaises(ValueError):
            pulse(states)

    def test_memory_history_disappearance_blocks(self):
        report = pulse(before=[event(1), event(2)], after=[event(2)])
        self.assertEqual(report["memory_status"], "blocked")
        self.assertIn("memory_continuity_conflict", report["blocking_review_reasons"])

    def test_report_deterministic(self):
        self.assertEqual(pulse(), pulse())

    def test_unknown_state_fails(self):
        states = dict.fromkeys(DOMAINS, "passed")
        states["media"] = "maybe"
        with self.assertRaises(ValueError):
            pulse(states)

    def test_no_false_service_health(self):
        report = pulse()
        self.assertFalse(report["service_health_checked"])
        self.assertFalse(report["tasks_dispatched"])
        self.assertFalse(report["cross_room_data_loaded"])

    def test_memory_report_digest_present(self):
        report = pulse()
        self.assertEqual(len(report["memory_report_sha256"]), 64)
        self.assertEqual(len(report["pulse_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
