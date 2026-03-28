from __future__ import annotations

import sys
from pathlib import Path
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from klone.ingest import ingest_dataset  # noqa: E402
from klone.memory import MemoryService, system_ingest_episode_id  # noqa: E402
from klone.repository import KloneRepository  # noqa: E402
from klone.schemas import DatasetIngestRequest, MemoryLlmContextPayloadRecord  # noqa: E402


class MemoryPhase2C3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.repository = KloneRepository(self.root / "phase_2c3.sqlite")
        self.repository.initialize()
        self.memory_service = MemoryService(self.repository)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_llm_context_payload_is_deterministic_and_read_only(self) -> None:
        result = self._ingest_dataset(
            label="Episode LLM Context",
            classification_level="personal",
            folder_name="episode_llm_context",
            files={"note.txt": "alpha"},
        )
        room_id = "restricted-room"
        ingest_run_id = result["run"]["id"]
        episode_id = system_ingest_episode_id(room_id=room_id, ingest_run_id=ingest_run_id)

        run_events = self.repository.list_memory_events(
            room_id=room_id,
            limit=50,
            offset=0,
            ingest_run_id=ingest_run_id,
        )
        ingest_started = next(row for row in run_events if row["event_type"] == "ingest_started")
        ingest_completed = next(row for row in run_events if row["event_type"] == "ingest_completed")

        self.memory_service.reject_episode(
            room_id=room_id,
            episode_id=episode_id,
            reason="llm_context_episode_reject",
        )
        self.memory_service.supersede_event(
            room_id=room_id,
            event_id=ingest_started["id"],
            superseded_by_event_id=ingest_completed["id"],
            reason="llm_context_supersede",
        )

        counts_before = self.repository.counts_for_room(room_id=room_id)
        internal_runs_before = self.repository.list_internal_runs(limit=20)

        payload_once = self.memory_service.prepare_llm_context_payload(
            room_id=room_id,
            episode_id=episode_id,
        )
        payload_twice = self.memory_service.prepare_llm_context_payload(
            room_id=room_id,
            episode_id=episode_id,
        )

        counts_after = self.repository.counts_for_room(room_id=room_id)
        internal_runs_after = self.repository.list_internal_runs(limit=20)

        self.assertIsInstance(payload_once, MemoryLlmContextPayloadRecord)
        self.assertEqual(payload_once.model_dump(), payload_twice.model_dump())
        self.assertEqual(counts_before, counts_after)
        self.assertEqual(internal_runs_before, internal_runs_after)
        self.assertFalse(payload_once.llm_call_performed)
        self.assertFalse(payload_once.memory_write_enabled)
        self.assertEqual(payload_once.interface_mode, "read_only_context")
        self.assertEqual(payload_once.room_id, room_id)
        self.assertEqual(payload_once.query_scope.scope_kind, "episode_detail")
        self.assertEqual(payload_once.query_scope.primary_episode_id, episode_id)
        self.assertEqual(
            [
                (item.memory_kind, item.memory_id, item.inclusion_reason)
                for item in payload_once.included_context
            ],
            [
                ("episode", episode_id, "requested_root_episode_detail"),
                ("event", str(ingest_started["id"]), "stored_episode_event_membership"),
                ("event", str(ingest_completed["id"]), "stored_episode_event_membership"),
            ],
        )
        self.assertEqual(payload_once.excluded_context, [])
        self.assertIn("bounded_by_read_only_source_linked_memory", payload_once.warnings)
        self.assertIn("no_llm_call_performed", payload_once.warnings)
        self.assertIn("memory_write_path_disabled", payload_once.warnings)
        self.assertEqual(payload_once.context_package.included_episodes[0].status, "rejected")
        self.assertEqual(payload_once.context_package.included_events[0].status, "superseded")

    def test_llm_context_payload_is_room_scoped_and_exposes_exact_context_visibility(self) -> None:
        restricted_result = self._ingest_dataset(
            label="Restricted Event LLM Context",
            classification_level="personal",
            folder_name="restricted_event_llm_context",
            files={"note.txt": "alpha"},
        )
        self._ingest_dataset(
            label="Public Event LLM Context",
            classification_level="public",
            folder_name="public_event_llm_context",
            files={"note.txt": "beta"},
        )

        restricted_room_id = "restricted-room"
        public_room_id = "public-room"
        restricted_run_id = restricted_result["run"]["id"]
        restricted_episode_id = system_ingest_episode_id(
            room_id=restricted_room_id,
            ingest_run_id=restricted_run_id,
        )

        restricted_events = self.repository.list_memory_events(
            room_id=restricted_room_id,
            limit=50,
            offset=0,
            ingest_run_id=restricted_run_id,
        )
        ingest_started = next(row for row in restricted_events if row["event_type"] == "ingest_started")
        ingest_completed = next(row for row in restricted_events if row["event_type"] == "ingest_completed")

        self.memory_service.supersede_event(
            room_id=restricted_room_id,
            event_id=ingest_started["id"],
            superseded_by_event_id=ingest_completed["id"],
            reason="llm_context_event_supersede",
        )

        payload = self.memory_service.prepare_llm_context_payload(
            room_id=restricted_room_id,
            event_id=ingest_started["id"],
        )

        self.assertEqual(payload.query_scope.scope_kind, "event_detail")
        self.assertEqual(payload.query_scope.primary_event_id, ingest_started["id"])
        self.assertEqual(
            [
                (item.memory_kind, item.memory_id, item.inclusion_reason)
                for item in payload.included_context
            ],
            [
                ("event", str(ingest_started["id"]), "requested_root_event_detail"),
                ("episode", restricted_episode_id, "stored_event_episode_membership"),
            ],
        )
        self.assertEqual(
            [
                (item.memory_kind, item.memory_id, item.exclusion_reason)
                for item in payload.excluded_context
            ],
            [
                (
                    "event",
                    str(ingest_completed["id"]),
                    "reachable_via_linked_episode_but_excluded_by_event_root_scope",
                )
            ],
        )
        self.assertEqual([item.id for item in payload.context_package.included_events], [ingest_started["id"]])
        self.assertEqual([item.id for item in payload.context_package.included_episodes], [restricted_episode_id])

        with self.assertRaises(ValueError):
            self.memory_service.prepare_llm_context_payload(
                room_id=public_room_id,
                event_id=ingest_started["id"],
            )

    def _ingest_dataset(
        self,
        *,
        label: str,
        classification_level: str,
        folder_name: str,
        files: dict[str, str],
    ) -> dict:
        folder = self.root / folder_name
        folder.mkdir(parents=True, exist_ok=True)
        for relative_name, content in files.items():
            target = folder / relative_name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

        request = DatasetIngestRequest(
            label=label,
            root_path=str(folder),
            collection="fixtures",
            classification_level=classification_level,
            description=f"Fixture dataset {label}",
        )
        return ingest_dataset(self.repository, request)


if __name__ == "__main__":
    unittest.main()
