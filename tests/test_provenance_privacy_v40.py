"""Synthetic provenance and read-only boundary checks, no external calls."""
import unittest
from unittest.mock import Mock
from test_memory_integration_v38_v39 import Fixture, ROOM, OTHER


class ProvenancePrivacyV40(Fixture, unittest.TestCase):
    def attach(self, event, name, room=ROOM):
        return self.repo.upsert_memory_provenance({
            "room_id": room, "owner_type": "event", "owner_id": str(event),
            "provenance_type": "source_lineage",
            "source_table": "synthetic_fixture", "source_record_id": name,
            "basis_type": "synthetic_fixture",
        })

    def answer(self, event, question="summarize this event", answerer=None):
        return self.memory.generate_read_only_llm_answer(
            room_id=ROOM, event_id=event, question=question, answerer=answerer)

    def test_reference_is_carried_to_default_answer(self):
        event = self.event("local")
        self.attach(event, "local")
        result = self.answer(event)
        self.assertTrue(result.supported)
        self.assertFalse(result.llm_call_performed)
        self.assertFalse(result.memory_write_enabled)
        self.assertEqual(result.source_backed_content[0].source_refs,
                         ["synthetic_fixture:local"])

    def test_missing_provenance_never_calls_answerer(self):
        event = self.event("unverified")
        answerer = Mock(side_effect=AssertionError("unexpected invocation"))
        self.assertFalse(self.answer(event, answerer=answerer).supported)
        answerer.assert_not_called()

    def test_unsupported_question_never_calls_answerer(self):
        event = self.event("local")
        self.attach(event, "local")
        answerer = Mock(side_effect=AssertionError("unexpected invocation"))
        self.assertFalse(self.answer(event, question="invent an unrelated story",
                                     answerer=answerer).supported)
        answerer.assert_not_called()

    def test_foreign_reference_rejected(self):
        event = self.event("local")
        other = self.event("foreign", room=OTHER)
        self.attach(event, "local")
        self.attach(other, "foreign", room=OTHER)
        answerer = Mock(return_value={"source_backed_content": [
            {"content": "synthetic", "source_refs": ["synthetic_fixture:foreign"]}]})
        with self.assertRaises(ValueError):
            self.answer(event, answerer=answerer)

    def test_missing_reference_rejected(self):
        event = self.event("local")
        self.attach(event, "local")
        answerer = Mock(return_value={"source_backed_content": [
            {"content": "synthetic", "source_refs": []}]})
        with self.assertRaises(ValueError):
            self.answer(event, answerer=answerer)

    def test_unrelated_room_not_in_context(self):
        event = self.event("local")
        other = self.event("other", room=OTHER)
        self.attach(event, "local")
        self.attach(other, "private-synthetic-marker", room=OTHER)
        payload = self.memory.prepare_llm_context_payload(room_id=ROOM, event_id=event)
        self.assertNotIn("private-synthetic-marker", payload.model_dump_json())
        self.assertEqual(payload.context_package.provenance_summary.source_refs,
                         ["synthetic_fixture:local"])

    def test_duplicate_provenance_is_idempotent(self):
        event = self.event("local")
        first, created = self.attach(event, "local")
        second, again = self.attach(event, "local")
        self.assertTrue(created)
        self.assertFalse(again)
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(self.detail(event)["provenance_summary"]["total_count"], 1)

    def test_read_only_context_does_not_change_records(self):
        event = self.event("local")
        self.attach(event, "local")
        before = self.detail(event)
        self.answer(event)
        self.memory.prepare_llm_context_payload(room_id=ROOM, event_id=event)
        self.assertEqual(before, self.detail(event))
