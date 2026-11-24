"""Memory Continuity v3.0 — deterministic no-authority regression tests."""
from dataclasses import replace
import copy
import json
import unittest

from klone.memory_continuity_v30 import (
    PublicMemoryEvent, project_public_memory_events,
    check_memory_continuity, verify_memory_continuity_report,
)

T0 = "2026-11-24T08:00:00+00:00"
T1 = "2026-11-24T08:01:00+00:00"
T2 = "2026-11-24T08:02:00+00:00"


def event(number, **kwargs):
    fields = {"event_id": number, "recorded_at": T0, "occurred_at": T0}
    fields.update(kwargs)
    return PublicMemoryEvent(**fields)


def rejected(number):
    return event(number, status="rejected", corrected_at=T2,
                 correction_reason="operator_reject", corrected_by_role="owner")


def superseded(number, successor):
    return event(number, status="superseded", corrected_at=T2,
                 superseded_by_id=successor, correction_reason="source_fix",
                 corrected_by_role="owner")


class MemoryContinuityV30Tests(unittest.TestCase):
    def test_same_snapshot(self):
        self.assertEqual(check_memory_continuity([event(1)], [event(1)])["continuity_status"],
                         "consistent_for_review")

    def test_permutation_invariant_report(self):
        before = [event(1), event(2)]
        after = [event(2), event(1)]
        self.assertEqual(check_memory_continuity(before, after),
                         check_memory_continuity(list(reversed(before)), list(reversed(after))))

    def test_new_event(self):
        result = check_memory_continuity([event(1)], [event(1), event(2)])
        self.assertEqual(result["changes"]["new"], 1)

    def test_rejection_preserves_history(self):
        result = check_memory_continuity([event(1)], [rejected(1)])
        self.assertEqual(result["changes"]["new_rejections"], 1)
        self.assertEqual(result["current_active_count"], 0)
        self.assertFalse(result["automatic_memory_reactivation_allowed"])

    def test_supersession_preserves_history(self):
        result = check_memory_continuity([event(1), event(2)],
                                         [superseded(1, 2), event(2)])
        self.assertEqual(result["changes"]["new_supersessions"], 1)
        self.assertEqual(result["current_corrected_count"], 1)

    def test_corrected_to_active_is_blocked(self):
        self.assertEqual(check_memory_continuity([rejected(1)], [event(1)])["problems"],
                         ["correction_rewritten_or_reactivated"])

    def test_supersession_reactivation_is_blocked(self):
        result = check_memory_continuity([superseded(1, 2), event(2)], [event(1), event(2)])
        self.assertEqual(result["continuity_status"], "blocked")

    def test_corrected_reason_rewrite_is_blocked(self):
        result = check_memory_continuity([rejected(1)],
                                         [replace(rejected(1), correction_reason="tampered")])
        self.assertIn("correction_rewritten_or_reactivated", result["problems"])

    def test_recorded_at_mutation_blocked(self):
        changed = event(1, recorded_at=T1)
        self.assertIn("historical_event_metadata_changed",
                      check_memory_continuity([event(1)], [changed])["problems"])

    def test_missing_event_detected(self):
        result = check_memory_continuity([event(1), event(2)], [event(2)])
        self.assertIn("previous_event_missing", result["problems"])

    def test_corrected_event_disappearance_detected(self):
        result = check_memory_continuity([rejected(1), event(2)], [event(2)])
        self.assertIn("previous_event_missing", result["problems"])

    def test_replacement_absence_denied(self):
        with self.assertRaisesRegex(ValueError, "missing_memory_replacement"):
            check_memory_continuity([event(1)], [superseded(1, 2)])

    def test_replacement_recorded_later_denied(self):
        with self.assertRaisesRegex(ValueError, "replacement_recorded_after_correction"):
            check_memory_continuity([event(1)], [superseded(1, 2), event(2, recorded_at="2026-11-24T08:03:00Z")])

    def test_supersession_cycle_denied(self):
        with self.assertRaisesRegex(ValueError, "memory_supersession_cycle"):
            check_memory_continuity([event(1)], [superseded(1, 2), superseded(2, 1)])

    def test_self_supersession_denied(self):
        with self.assertRaisesRegex(ValueError, "invalid_replacement_event"):
            superseded(1, 1)

    def test_duplicate_event_id_denied(self):
        with self.assertRaisesRegex(ValueError, "duplicate_memory_event"):
            check_memory_continuity([event(1), event(1)], [event(1)])

    def test_no_private_room(self):
        with self.assertRaisesRegex(ValueError, "nonpublic_memory"):
            event(1, room_id="sealed-room", classification_level="intimate")

    def test_no_naive_timestamp(self):
        with self.assertRaisesRegex(ValueError, "timezone_required"):
            event(1, recorded_at="2026-11-24T09:00:00")

    def test_time_normalization_utc(self):
        self.assertEqual(event(1).recorded_at,
                         event(1, recorded_at="2026-11-24T10:00:00+02:00").recorded_at)

    def test_status_corrected_flag_mismatch_denied(self):
        row = self._row(1)
        row["corrected"] = True
        with self.assertRaisesRegex(ValueError, "corrected_flag_inconsistent"):
            project_public_memory_events([row])

    def test_public_projection_omits_private_fields(self):
        row = self._row(1)
        row["evidence_text"] = "SENSITIVE-FALSE-POSITIVE"
        result = project_public_memory_events([row])
        self.assertNotIn("SENSITIVE-FALSE-POSITIVE", repr(result))

    def test_private_projection_denied(self):
        row = self._row(1)
        row["room_id"] = "sandbox-room"
        row["classification_level"] = "restricted_bio"
        with self.assertRaises(ValueError):
            project_public_memory_events([row])

    def test_projection_metadata_required(self):
        with self.assertRaisesRegex(ValueError, "missing_memory_metadata"):
            project_public_memory_events([{"id": 1}])

    def test_bool_id_denied(self):
        with self.assertRaisesRegex(ValueError, "invalid_memory_event_id"):
            event(True)

    def test_active_with_correction_denied(self):
        with self.assertRaisesRegex(ValueError, "active_memory_has_correction_metadata"):
            event(1, corrected_at=T2)

    def test_missing_correction_reason_denied(self):
        with self.assertRaisesRegex(ValueError, "incomplete_correction_metadata"):
            event(1, status="rejected", corrected_at=T2)

    def test_correction_before_recorded_denied(self):
        with self.assertRaisesRegex(ValueError, "correction_before_recording_or_missing"):
            event(1, status="rejected", recorded_at=T2, corrected_at=T1,
                  correction_reason="invalid", corrected_by_role="owner")

    def test_replay_matches_and_detects_report_mutation(self):
        result = check_memory_continuity([event(1)], [rejected(1)])
        self.assertTrue(verify_memory_continuity_report([event(1)], [rejected(1)], result))
        changed = copy.deepcopy(result)
        changed["changes"]["new_rejections"] = 0
        self.assertFalse(verify_memory_continuity_report([event(1)], [rejected(1)], changed))

    def test_replay_rejects_nonserializable_report(self):
        self.assertFalse(verify_memory_continuity_report([event(1)], [event(1)],
                                                         {"broken": object()}))

    def test_snapshot_not_execution_or_authentication(self):
        result = check_memory_continuity([event(1)], [rejected(1)])
        self.assertFalse(result["source_snapshot_authenticated"])
        self.assertFalse(result["deployment_approval"])
        self.assertTrue(result["manual_review_required"])

    def test_no_raw_data_in_report(self):
        result = check_memory_continuity([event(1)], [rejected(1)])
        text = json.dumps(result)
        self.assertNotIn("operator_reject", text)
        self.assertNotIn("evidence_text", text)

    @staticmethod
    def _row(i):
        return {"id": i, "room_id": "public-room", "classification_level": "public",
                "recorded_at": T0, "occurred_at": T0, "status": "active"}


if __name__ == "__main__":
    unittest.main()
