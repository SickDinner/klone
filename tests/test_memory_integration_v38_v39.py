"""Synthetic SQLite integration tests; no production database or model calls."""
import tempfile
import unittest
from pathlib import Path

from klone.memory import MemoryService
from klone.repository import KloneRepository
from test_memory_evidence_contract_v37 import evaluate

ROOM = "restricted-room"
OTHER = "debug-room"


class Fixture:
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "synthetic.sqlite3"
        self.repo = KloneRepository(self.path)
        self.repo.initialize()
        self.memory = MemoryService(self.repo)

    def event(self, name, day=1, room=ROOM):
        date = f"2026-01-{day:02d}T00:00:00+00:00"
        row, created = self.repo.upsert_memory_event({
            "room_id": room,
            "classification_level": "personal" if room == ROOM else "intimate",
            "event_type": "synthetic_observation",
            "source_table": "synthetic_fixture",
            "source_record_id": name,
            "occurred_at": date,
            "recorded_at": date,
            "title": name,
            "evidence_text": "synthetic: " + name,
        })
        self.assertTrue(created)
        return row["id"]

    def detail(self, event_id, room=ROOM):
        return self.memory.get_event_detail(room_id=room, event_id=event_id)

    def visible(self, corrected=False):
        return [r["id"] for r in self.memory.query_events(
            room_id=ROOM, limit=100, offset=0, include_corrected=corrected)]

    def replace(self, old, new, reason="synthetic correction"):
        return self.memory.supersede_event(room_id=ROOM, event_id=old,
                                          superseded_by_event_id=new, reason=reason)

    def reject(self, event_id, reason="synthetic rejection"):
        return self.memory.reject_event(room_id=ROOM, event_id=event_id, reason=reason)


class MemoryIntegrationV38(Fixture, unittest.TestCase):
    def test_room_scoped_query_and_detail(self):
        local = self.event("local")
        other = self.event("other", room=OTHER)
        self.assertEqual(self.visible(), [local])
        self.assertIsNone(self.detail(other))
        self.assertIsNone(self.detail(local, OTHER))

    def test_wrong_room_context_rejected(self):
        other = self.event("other", room=OTHER)
        with self.assertRaises(ValueError):
            self.memory.assemble_context_package(room_id=ROOM, event_id=other)

    def test_cross_room_replacement_rejected(self):
        old = self.event("old")
        other = self.event("other", room=OTHER)
        with self.assertRaises(ValueError):
            self.replace(old, other)
        self.assertEqual(self.detail(old)["status"], "active")

    def test_missing_provenance_abstention(self):
        event = self.event("unverified")
        answer = self.memory.generate_read_only_llm_answer(
            room_id=ROOM, event_id=event, question="summarize this event")
        self.assertFalse(answer.supported)
        self.assertFalse(answer.llm_call_performed)
        self.assertFalse(answer.memory_write_enabled)

    def test_context_read_only_flags(self):
        event = self.event("local")
        payload = self.memory.prepare_llm_context_payload(room_id=ROOM, event_id=event)
        self.assertFalse(payload.llm_call_performed)
        self.assertFalse(payload.memory_write_enabled)
        self.assertEqual([e.id for e in payload.context_package.included_events], [event])

    def test_synthetic_scorer_on_observed_statuses(self):
        current = self.event("current")
        old = self.event("old")
        rejected = self.event("rejected")
        other = self.event("other", room=OTHER)
        self.replace(old, current)
        self.reject(rejected)
        # Active is not proof of truth. Here it means only fixture state.
        def state(event):
            row = self.detail(event)
            if row is None:
                return "blocked"
            return "stale" if row["corrected"] else "supported"
        expected = [("current", "supported"), ("old", "stale"),
                    ("rejected", "stale"), ("other", "blocked")]
        observed = [(name, state(event)) for name, event in
                    [("current", current), ("old", old),
                     ("rejected", rejected), ("other", other)]]
        self.assertTrue(evaluate(expected, observed)["passed"])


class TemporalMemoryV39(Fixture, unittest.TestCase):
    def test_order_by_occurrence_not_insertion(self):
        newer = self.event("newer", 2)
        older = self.event("older", 1)
        self.assertEqual(self.visible(), [newer, older])

    def test_superseded_excluded_from_active_query(self):
        old = self.event("old", 1)
        new = self.event("new", 2)
        self.replace(old, new)
        self.assertEqual(self.visible(), [new])
        self.assertEqual(self.visible(True), [new, old])
        self.assertEqual(self.detail(old)["superseded_by_id"], new)

    def test_rejected_history_preserved(self):
        old = self.event("old")
        self.reject(old)
        self.assertEqual(self.visible(), [])
        self.assertEqual(self.visible(True), [old])
        self.assertTrue(self.detail(old)["corrected"])
        self.assertEqual(self.detail(old)["evidence_text"], "synthetic: old")

    def test_repeat_correction_preserves_timestamp(self):
        old = self.event("old")
        new = self.event("new")
        first = self.replace(old, new)
        second = self.replace(old, new)
        self.assertEqual(first.corrected_at, second.corrected_at)
        self.assertEqual(second.superseded_by_id, new)

    def test_context_reports_correction(self):
        old = self.event("old")
        new = self.event("new")
        self.replace(old, new)
        package = self.memory.assemble_context_package(room_id=ROOM, event_id=old)
        self.assertEqual(package.correction_summary.superseded_event_ids, [old])
        self.assertTrue(package.included_events[0].corrected)

    def test_reopen_preserves_correction(self):
        old = self.event("old")
        self.reject(old)
        reopened = MemoryService(KloneRepository(self.path))
        row = reopened.get_event_detail(room_id=ROOM, event_id=old)
        self.assertEqual(row["status"], "rejected")
        self.assertTrue(row["corrected"])
