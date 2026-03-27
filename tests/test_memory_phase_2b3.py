from __future__ import annotations

import json
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
from klone.schemas import DatasetIngestRequest  # noqa: E402


class MemoryPhase2B3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.repository = KloneRepository(self.root / "phase_2b3.sqlite")
        self.repository.initialize()
        self.memory_service = MemoryService(self.repository)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_corrections_remain_queryable_and_survive_replay(self) -> None:
        result = self._ingest_dataset(
            label="Restricted Dataset",
            classification_level="personal",
            folder_name="restricted_dataset",
            files={"note.txt": "alpha", "photo.jpg": "beta"},
        )
        room_id = "restricted-room"
        ingest_run_id = result["run"]["id"]
        episode_id = system_ingest_episode_id(room_id=room_id, ingest_run_id=ingest_run_id)

        event_rows = self.repository.list_memory_events(room_id=room_id, limit=50, offset=0)
        ingest_requested = next(row for row in event_rows if row["event_type"] == "ingest_requested")
        ingest_started = next(row for row in event_rows if row["event_type"] == "ingest_started")
        ingest_completed = next(row for row in event_rows if row["event_type"] == "ingest_completed")

        completed_before = self.memory_service.get_event_detail(
            room_id=room_id,
            event_id=ingest_requested["id"],
        )
        started_before = self.memory_service.get_event_detail(
            room_id=room_id,
            event_id=ingest_started["id"],
        )
        episode_before = self.memory_service.get_episode_detail(
            room_id=room_id,
            episode_id=episode_id,
        )

        self.assertFalse(completed_before["corrected"])
        self.assertFalse(started_before["corrected"])

        reject_event_result = self.memory_service.reject_event(
            room_id=room_id,
            event_id=ingest_requested["id"],
            reason="operator_reject",
        )
        reject_episode_result = self.memory_service.reject_episode(
            room_id=room_id,
            episode_id=episode_id,
            reason="operator_episode_reject",
        )
        supersede_result = self.memory_service.supersede_event(
            room_id=room_id,
            event_id=ingest_started["id"],
            superseded_by_event_id=ingest_completed["id"],
            reason="operator_supersede",
        )

        repeat_reject_result = self.memory_service.reject_event(
            room_id=room_id,
            event_id=ingest_requested["id"],
            reason="operator_reject",
        )
        repeat_supersede_result = self.memory_service.supersede_event(
            room_id=room_id,
            event_id=ingest_started["id"],
            superseded_by_event_id=ingest_completed["id"],
            reason="operator_supersede",
        )

        completed_after = self.memory_service.get_event_detail(
            room_id=room_id,
            event_id=ingest_requested["id"],
        )
        started_after = self.memory_service.get_event_detail(
            room_id=room_id,
            event_id=ingest_started["id"],
        )
        episode_after = self.memory_service.get_episode_detail(
            room_id=room_id,
            episode_id=episode_id,
        )

        self.assertEqual(reject_event_result.resulting_status, "rejected")
        self.assertEqual(reject_episode_result.resulting_status, "rejected")
        self.assertEqual(supersede_result.resulting_status, "superseded")
        self.assertEqual(repeat_reject_result.resulting_status, "rejected")
        self.assertEqual(repeat_supersede_result.resulting_status, "superseded")
        self.assertEqual(reject_event_result.corrected_at, repeat_reject_result.corrected_at)
        self.assertEqual(supersede_result.corrected_at, repeat_supersede_result.corrected_at)

        self.assertEqual(completed_after["status"], "rejected")
        self.assertEqual(completed_after["correction_reason"], "operator_reject")
        self.assertEqual(completed_after["corrected_by_role"], "owner")
        self.assertTrue(completed_after["corrected"])
        self.assertEqual(completed_after["evidence_text"], completed_before["evidence_text"])
        self.assertTrue(completed_after["provenance"])

        self.assertEqual(started_after["status"], "superseded")
        self.assertEqual(started_after["superseded_by_id"], ingest_completed["id"])
        self.assertEqual(started_after["correction_reason"], "operator_supersede")
        self.assertTrue(started_after["corrected"])
        self.assertEqual(started_after["evidence_text"], started_before["evidence_text"])
        self.assertTrue(started_after["provenance"])

        self.assertEqual(episode_after["status"], "rejected")
        self.assertEqual(episode_after["correction_reason"], "operator_episode_reject")
        self.assertEqual(episode_after["corrected_by_role"], "owner")
        self.assertTrue(episode_after["provenance"])

        member_statuses = {member["event"]["id"]: member["event"]["status"] for member in episode_after["linked_events"]}
        self.assertEqual(member_statuses[ingest_started["id"]], "superseded")
        self.assertEqual(member_statuses[ingest_completed["id"]], "active")

        supersede_audits = [
            row
            for row in self.repository.list_audit_events(room_id=room_id, limit=400)
            if row["event_type"] == "memory_correction_completed"
            and json.loads(row["metadata_json"])["operation"] == "supersede_event"
            and json.loads(row["metadata_json"])["memory_id"] == str(ingest_started["id"])
        ]
        self.assertTrue(supersede_audits)

        correction_state_before_replay = {
            "event_status": completed_after["status"],
            "event_reason": completed_after["correction_reason"],
            "episode_status": episode_after["status"],
            "episode_reason": episode_after["correction_reason"],
            "superseded_status": started_after["status"],
            "superseded_by_id": started_after["superseded_by_id"],
            "event_provenance": completed_after["provenance"],
            "episode_provenance": episode_after["provenance"],
        }

        replay_result = self.memory_service.replay_memory_generation(
            room_id=room_id,
            ingest_run_id=ingest_run_id,
        )

        completed_after_replay = self.memory_service.get_event_detail(
            room_id=room_id,
            event_id=ingest_requested["id"],
        )
        started_after_replay = self.memory_service.get_event_detail(
            room_id=room_id,
            event_id=ingest_started["id"],
        )
        episode_after_replay = self.memory_service.get_episode_detail(
            room_id=room_id,
            episode_id=episode_id,
        )

        self.assertEqual(replay_result.room_id, room_id)
        self.assertEqual(replay_result.ingest_run_id, ingest_run_id)
        self.assertEqual(completed_after_replay["status"], correction_state_before_replay["event_status"])
        self.assertEqual(completed_after_replay["correction_reason"], correction_state_before_replay["event_reason"])
        self.assertTrue(completed_after_replay["corrected"])
        self.assertEqual(completed_after_replay["evidence_text"], completed_before["evidence_text"])
        self.assertEqual(started_after_replay["status"], correction_state_before_replay["superseded_status"])
        self.assertEqual(started_after_replay["superseded_by_id"], correction_state_before_replay["superseded_by_id"])
        self.assertTrue(started_after_replay["corrected"])
        self.assertEqual(started_after_replay["evidence_text"], started_before["evidence_text"])
        self.assertEqual(episode_after_replay["status"], correction_state_before_replay["episode_status"])
        self.assertEqual(episode_after_replay["correction_reason"], correction_state_before_replay["episode_reason"])
        self.assertEqual(completed_after_replay["provenance"], correction_state_before_replay["event_provenance"])
        self.assertEqual(episode_after_replay["provenance"], correction_state_before_replay["episode_provenance"])
        self.assertEqual(episode_id, system_ingest_episode_id(room_id=room_id, ingest_run_id=ingest_run_id))

    def test_room_isolation_and_cross_room_supersede_blocking(self) -> None:
        restricted_result = self._ingest_dataset(
            label="Restricted Dataset",
            classification_level="personal",
            folder_name="restricted_dataset",
            files={"note.txt": "alpha"},
        )
        public_result = self._ingest_dataset(
            label="Public Dataset",
            classification_level="public",
            folder_name="public_dataset",
            files={"note.txt": "beta"},
        )

        restricted_room_id = "restricted-room"
        public_room_id = "public-room"
        restricted_run_id = restricted_result["run"]["id"]
        public_run_id = public_result["run"]["id"]

        restricted_started = next(
            row
            for row in self.repository.list_memory_events(room_id=restricted_room_id, limit=50, offset=0)
            if row["event_type"] == "ingest_started"
        )
        restricted_completed = next(
            row
            for row in self.repository.list_memory_events(room_id=restricted_room_id, limit=50, offset=0)
            if row["event_type"] == "ingest_completed"
        )
        public_started = next(
            row
            for row in self.repository.list_memory_events(room_id=public_room_id, limit=50, offset=0)
            if row["event_type"] == "ingest_started"
        )
        public_completed = next(
            row
            for row in self.repository.list_memory_events(room_id=public_room_id, limit=50, offset=0)
            if row["event_type"] == "ingest_completed"
        )

        self.memory_service.reject_event(
            room_id=restricted_room_id,
            event_id=restricted_completed["id"],
            reason="room_isolation_reject",
        )
        with self.assertRaises(ValueError):
            self.memory_service.supersede_event(
                room_id=restricted_room_id,
                event_id=restricted_started["id"],
                superseded_by_event_id=public_started["id"],
                reason="cross_room_supersede",
            )

        restricted_detail = self.memory_service.get_event_detail(
            room_id=restricted_room_id,
            event_id=restricted_completed["id"],
        )
        public_detail = self.memory_service.get_event_detail(
            room_id=public_room_id,
            event_id=public_completed["id"],
        )

        self.assertEqual(restricted_detail["status"], "rejected")
        self.assertEqual(public_detail["status"], "active")
        self.assertIsNone(
            self.memory_service.get_event_detail(
                room_id=public_room_id,
                event_id=restricted_completed["id"],
            )
        )

        replay_result = self.memory_service.replay_memory_generation(
            room_id=restricted_room_id,
            ingest_run_id=restricted_run_id,
        )
        public_episode_id = system_ingest_episode_id(room_id=public_room_id, ingest_run_id=public_run_id)
        public_episode_detail = self.memory_service.get_episode_detail(
            room_id=public_room_id,
            episode_id=public_episode_id,
        )
        blocked_audits = [
            row
            for row in self.repository.list_audit_events(room_id=restricted_room_id, limit=400)
            if row["event_type"] == "memory_correction_blocked"
        ]

        self.assertEqual(replay_result.room_id, restricted_room_id)
        self.assertEqual(replay_result.ingest_run_id, restricted_run_id)
        self.assertEqual(public_detail["evidence_text"], self.memory_service.get_event_detail(
            room_id=public_room_id,
            event_id=public_completed["id"],
        )["evidence_text"])
        self.assertEqual(public_episode_detail["status"], "active")
        self.assertTrue(blocked_audits)
        blocked_payload = json.loads(blocked_audits[0]["metadata_json"])
        self.assertEqual(blocked_payload["operation"], "supersede_event")
        self.assertEqual(blocked_payload["reason"], "cross_room_supersede")
        self.assertEqual(blocked_payload["actor_role"], "owner")
        self.assertEqual(blocked_payload["superseded_by_id"], public_started["id"])

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
