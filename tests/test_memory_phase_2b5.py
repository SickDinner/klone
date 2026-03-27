from __future__ import annotations

import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from klone.api import memory_episode_detail, memory_episode_events, memory_event_detail  # noqa: E402
from klone.ingest import ingest_dataset  # noqa: E402
from klone.memory import MemoryService, system_ingest_episode_id  # noqa: E402
from klone.repository import KloneRepository, utc_now_iso  # noqa: E402
from klone.schemas import DatasetIngestRequest  # noqa: E402


class MemoryPhase2B5Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.repository = KloneRepository(self.root / "phase_2b5.sqlite")
        self.repository.initialize()
        self.memory_service = MemoryService(self.repository)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_replay_after_reject_event_preserves_status_and_evidence(self) -> None:
        result = self._ingest_dataset(
            label="Restricted Replay Reject Event",
            classification_level="personal",
            folder_name="restricted_replay_reject_event",
            files={"note.txt": "alpha"},
        )
        room_id = "restricted-room"
        ingest_run_id = result["run"]["id"]
        rejected_event = self._event_by_type(
            room_id=room_id,
            event_type="ingest_completed",
            ingest_run_id=ingest_run_id,
        )

        before_detail = self.memory_service.get_event_detail(room_id=room_id, event_id=rejected_event["id"])
        self.assertIsNotNone(before_detail)

        self.memory_service.replay_memory_generation(room_id=room_id, ingest_run_id=ingest_run_id)
        correction = self.memory_service.reject_event(
            room_id=room_id,
            event_id=rejected_event["id"],
            reason="stress_reject_event",
        )
        self.assertEqual(correction.resulting_status, "rejected")

        after_correction = self.memory_service.get_event_detail(room_id=room_id, event_id=rejected_event["id"])
        scoped_replay = self.memory_service.replay_memory_generation(room_id=room_id, ingest_run_id=ingest_run_id)
        after_scoped_replay = self.memory_service.get_event_detail(room_id=room_id, event_id=rejected_event["id"])
        room_replay = self.memory_service.replay_memory_generation(room_id=room_id)
        after_room_replay = self.memory_service.get_event_detail(room_id=room_id, event_id=rejected_event["id"])

        self.assertEqual(scoped_replay.ingest_run_id, ingest_run_id)
        self.assertIsNone(room_replay.ingest_run_id)
        self.assertEqual(after_correction["status"], "rejected")
        self.assertEqual(after_scoped_replay["status"], "rejected")
        self.assertEqual(after_room_replay["status"], "rejected")
        self.assertEqual(before_detail["evidence_text"], after_correction["evidence_text"])
        self.assertEqual(before_detail["evidence_text"], after_scoped_replay["evidence_text"])
        self.assertEqual(before_detail["evidence_text"], after_room_replay["evidence_text"])
        self.assertEqual(before_detail["source_lineage"], after_scoped_replay["source_lineage"])
        self.assertEqual(before_detail["source_lineage"], after_room_replay["source_lineage"])
        self.assertEqual(before_detail["provenance"], after_scoped_replay["provenance"])
        self.assertEqual(before_detail["provenance"], after_room_replay["provenance"])

    def test_replay_after_reject_episode_preserves_status_and_evidence(self) -> None:
        result = self._ingest_dataset(
            label="Restricted Replay Reject Episode",
            classification_level="personal",
            folder_name="restricted_replay_reject_episode",
            files={"note.txt": "alpha", "photo.jpg": "beta"},
        )
        room_id = "restricted-room"
        ingest_run_id = result["run"]["id"]
        episode_id = system_ingest_episode_id(room_id=room_id, ingest_run_id=ingest_run_id)

        before_episode = self.memory_service.get_episode_detail(room_id=room_id, episode_id=episode_id)
        self.assertIsNotNone(before_episode)
        before_member_evidence = {
            member["event"]["id"]: member["event"]["evidence_text"] for member in before_episode["linked_events"]
        }

        correction = self.memory_service.reject_episode(
            room_id=room_id,
            episode_id=episode_id,
            reason="stress_reject_episode",
        )
        self.assertEqual(correction.resulting_status, "rejected")

        after_correction = self.memory_service.get_episode_detail(room_id=room_id, episode_id=episode_id)
        self.memory_service.replay_memory_generation(room_id=room_id, ingest_run_id=ingest_run_id)
        after_scoped_replay = self.memory_service.get_episode_detail(room_id=room_id, episode_id=episode_id)
        self.memory_service.replay_memory_generation(room_id=room_id)
        after_room_replay = self.memory_service.get_episode_detail(room_id=room_id, episode_id=episode_id)

        self.assertEqual(after_correction["status"], "rejected")
        self.assertEqual(after_scoped_replay["status"], "rejected")
        self.assertEqual(after_room_replay["status"], "rejected")
        self.assertEqual(before_episode["source_lineage"], after_scoped_replay["source_lineage"])
        self.assertEqual(before_episode["source_lineage"], after_room_replay["source_lineage"])
        self.assertEqual(before_episode["membership_basis"], after_scoped_replay["membership_basis"])
        self.assertEqual(before_episode["membership_basis"], after_room_replay["membership_basis"])
        self.assertEqual(before_episode["provenance"], after_scoped_replay["provenance"])
        self.assertEqual(before_episode["provenance"], after_room_replay["provenance"])
        self.assertEqual(
            before_member_evidence,
            {member["event"]["id"]: member["event"]["evidence_text"] for member in after_correction["linked_events"]},
        )
        self.assertEqual(
            before_member_evidence,
            {member["event"]["id"]: member["event"]["evidence_text"] for member in after_scoped_replay["linked_events"]},
        )
        self.assertEqual(
            before_member_evidence,
            {member["event"]["id"]: member["event"]["evidence_text"] for member in after_room_replay["linked_events"]},
        )

    def test_replay_after_supersede_event_preserves_status_target_and_provenance(self) -> None:
        result = self._ingest_dataset(
            label="Restricted Replay Supersede Event",
            classification_level="personal",
            folder_name="restricted_replay_supersede_event",
            files={"note.txt": "alpha"},
        )
        room_id = "restricted-room"
        ingest_run_id = result["run"]["id"]
        started = self._event_by_type(room_id=room_id, event_type="ingest_started", ingest_run_id=ingest_run_id)
        completed = self._event_by_type(room_id=room_id, event_type="ingest_completed", ingest_run_id=ingest_run_id)

        before_detail = self.memory_service.get_event_detail(room_id=room_id, event_id=started["id"])
        correction = self.memory_service.supersede_event(
            room_id=room_id,
            event_id=started["id"],
            superseded_by_event_id=completed["id"],
            reason="stress_supersede_event",
        )
        after_correction = self.memory_service.get_event_detail(room_id=room_id, event_id=started["id"])
        self.memory_service.replay_memory_generation(room_id=room_id, ingest_run_id=ingest_run_id)
        after_scoped_replay = self.memory_service.get_event_detail(room_id=room_id, event_id=started["id"])
        self.memory_service.replay_memory_generation(room_id=room_id)
        after_room_replay = self.memory_service.get_event_detail(room_id=room_id, event_id=started["id"])

        self.assertEqual(correction.resulting_status, "superseded")
        self.assertEqual(after_correction["status"], "superseded")
        self.assertEqual(after_scoped_replay["status"], "superseded")
        self.assertEqual(after_room_replay["status"], "superseded")
        self.assertEqual(after_correction["superseded_by_id"], completed["id"])
        self.assertEqual(after_scoped_replay["superseded_by_id"], completed["id"])
        self.assertEqual(after_room_replay["superseded_by_id"], completed["id"])
        self.assertEqual(before_detail["evidence_text"], after_correction["evidence_text"])
        self.assertEqual(before_detail["evidence_text"], after_scoped_replay["evidence_text"])
        self.assertEqual(before_detail["evidence_text"], after_room_replay["evidence_text"])
        self.assertEqual(before_detail["source_lineage"], after_scoped_replay["source_lineage"])
        self.assertEqual(before_detail["source_lineage"], after_room_replay["source_lineage"])
        self.assertEqual(before_detail["provenance"], after_scoped_replay["provenance"])
        self.assertEqual(before_detail["provenance"], after_room_replay["provenance"])
        self.assertEqual(self._count_supersession_rows(room_id=room_id, old_event_id=started["id"]), 1)

    def test_repeated_reject_is_idempotent(self) -> None:
        result = self._ingest_dataset(
            label="Repeated Reject",
            classification_level="personal",
            folder_name="repeated_reject",
            files={"note.txt": "alpha"},
        )
        room_id = "restricted-room"
        ingest_run_id = result["run"]["id"]
        target = self._event_by_type(room_id=room_id, event_type="ingest_started", ingest_run_id=ingest_run_id)

        first = self.memory_service.reject_event(
            room_id=room_id,
            event_id=target["id"],
            reason="idempotent_reject",
        )
        second = self.memory_service.reject_event(
            room_id=room_id,
            event_id=target["id"],
            reason="idempotent_reject",
        )
        detail = self.memory_service.get_event_detail(room_id=room_id, event_id=target["id"])

        self.assertEqual(first.corrected_at, second.corrected_at)
        self.assertEqual(first.resulting_status, second.resulting_status)
        self.assertEqual(detail["status"], "rejected")
        self.assertEqual(detail["correction_reason"], "idempotent_reject")

    def test_repeated_supersede_same_target_is_idempotent(self) -> None:
        result = self._ingest_dataset(
            label="Repeated Supersede",
            classification_level="personal",
            folder_name="repeated_supersede",
            files={"note.txt": "alpha"},
        )
        room_id = "restricted-room"
        ingest_run_id = result["run"]["id"]
        old_event = self._event_by_type(room_id=room_id, event_type="ingest_started", ingest_run_id=ingest_run_id)
        new_event = self._event_by_type(room_id=room_id, event_type="ingest_completed", ingest_run_id=ingest_run_id)

        first = self.memory_service.supersede_event(
            room_id=room_id,
            event_id=old_event["id"],
            superseded_by_event_id=new_event["id"],
            reason="idempotent_supersede",
        )
        second = self.memory_service.supersede_event(
            room_id=room_id,
            event_id=old_event["id"],
            superseded_by_event_id=new_event["id"],
            reason="idempotent_supersede",
        )
        detail = self.memory_service.get_event_detail(room_id=room_id, event_id=old_event["id"])

        self.assertEqual(first.corrected_at, second.corrected_at)
        self.assertEqual(first.superseded_by_id, second.superseded_by_id)
        self.assertEqual(detail["status"], "superseded")
        self.assertEqual(detail["superseded_by_id"], new_event["id"])
        self.assertEqual(self._count_supersession_rows(room_id=room_id, old_event_id=old_event["id"]), 1)

    def test_scoped_replay_does_not_touch_other_ingest_run_in_same_room(self) -> None:
        first_result = self._ingest_dataset(
            label="Scoped Replay One",
            classification_level="personal",
            folder_name="scoped_replay_one",
            files={"a.txt": "one"},
        )
        second_result = self._ingest_dataset(
            label="Scoped Replay Two",
            classification_level="personal",
            folder_name="scoped_replay_two",
            files={"b.txt": "two"},
        )
        room_id = "restricted-room"
        first_run_id = first_result["run"]["id"]
        second_run_id = second_result["run"]["id"]
        first_episode_id = system_ingest_episode_id(room_id=room_id, ingest_run_id=first_run_id)
        second_episode_id = system_ingest_episode_id(room_id=room_id, ingest_run_id=second_run_id)
        second_completed = self._event_by_type(
            room_id=room_id,
            event_type="ingest_completed",
            ingest_run_id=second_run_id,
        )

        self.memory_service.reject_episode(
            room_id=room_id,
            episode_id=second_episode_id,
            reason="other_run_episode_reject",
        )
        self.memory_service.reject_event(
            room_id=room_id,
            event_id=second_completed["id"],
            reason="other_run_event_reject",
        )

        first_before = self.memory_service.get_episode_detail(room_id=room_id, episode_id=first_episode_id)
        second_before = self.memory_service.get_episode_detail(room_id=room_id, episode_id=second_episode_id)
        second_event_before = self.memory_service.get_event_detail(room_id=room_id, event_id=second_completed["id"])

        replay_result = self.memory_service.replay_memory_generation(
            room_id=room_id,
            ingest_run_id=first_run_id,
        )

        first_after = self.memory_service.get_episode_detail(room_id=room_id, episode_id=first_episode_id)
        second_after = self.memory_service.get_episode_detail(room_id=room_id, episode_id=second_episode_id)
        second_event_after = self.memory_service.get_event_detail(room_id=room_id, event_id=second_completed["id"])

        self.assertEqual(replay_result.ingest_run_id, first_run_id)
        self.assertEqual(first_before["linked_events"], first_after["linked_events"])
        self.assertEqual(second_before["status"], second_after["status"])
        self.assertEqual(second_before["correction_reason"], second_after["correction_reason"])
        self.assertEqual(second_before["linked_events"], second_after["linked_events"])
        self.assertEqual(second_before["membership_basis"], second_after["membership_basis"])
        self.assertEqual(second_event_before["status"], second_event_after["status"])
        self.assertEqual(second_event_before["correction_reason"], second_event_after["correction_reason"])
        self.assertEqual(second_event_before["evidence_text"], second_event_after["evidence_text"])

    def test_correction_in_room_a_does_not_affect_room_b(self) -> None:
        restricted_result = self._ingest_dataset(
            label="Restricted Correction Room",
            classification_level="personal",
            folder_name="restricted_correction_room",
            files={"note.txt": "alpha"},
        )
        public_result = self._ingest_dataset(
            label="Public Correction Room",
            classification_level="public",
            folder_name="public_correction_room",
            files={"note.txt": "beta"},
        )
        restricted_room_id = "restricted-room"
        public_room_id = "public-room"
        restricted_run_id = restricted_result["run"]["id"]
        public_run_id = public_result["run"]["id"]
        restricted_completed = self._event_by_type(
            room_id=restricted_room_id,
            event_type="ingest_completed",
            ingest_run_id=restricted_run_id,
        )
        public_completed = self._event_by_type(
            room_id=public_room_id,
            event_type="ingest_completed",
            ingest_run_id=public_run_id,
        )
        public_episode_id = system_ingest_episode_id(room_id=public_room_id, ingest_run_id=public_run_id)

        public_event_before = self.memory_service.get_event_detail(room_id=public_room_id, event_id=public_completed["id"])
        public_episode_before = self.memory_service.get_episode_detail(room_id=public_room_id, episode_id=public_episode_id)

        self.memory_service.reject_event(
            room_id=restricted_room_id,
            event_id=restricted_completed["id"],
            reason="restricted_only_reject",
        )
        self.memory_service.replay_memory_generation(room_id=restricted_room_id)

        public_event_after = self.memory_service.get_event_detail(room_id=public_room_id, event_id=public_completed["id"])
        public_episode_after = self.memory_service.get_episode_detail(room_id=public_room_id, episode_id=public_episode_id)

        self.assertEqual(public_event_before, public_event_after)
        self.assertEqual(public_episode_before, public_episode_after)

    def test_cross_room_supersede_is_blocked(self) -> None:
        restricted_result = self._ingest_dataset(
            label="Restricted Cross Room",
            classification_level="personal",
            folder_name="restricted_cross_room",
            files={"note.txt": "alpha"},
        )
        public_result = self._ingest_dataset(
            label="Public Cross Room",
            classification_level="public",
            folder_name="public_cross_room",
            files={"note.txt": "beta"},
        )
        restricted_room_id = "restricted-room"
        public_room_id = "public-room"
        restricted_started = self._event_by_type(
            room_id=restricted_room_id,
            event_type="ingest_started",
            ingest_run_id=restricted_result["run"]["id"],
        )
        public_completed = self._event_by_type(
            room_id=public_room_id,
            event_type="ingest_completed",
            ingest_run_id=public_result["run"]["id"],
        )

        with self.assertRaises(ValueError):
            self.memory_service.supersede_event(
                room_id=restricted_room_id,
                event_id=restricted_started["id"],
                superseded_by_event_id=public_completed["id"],
                reason="cross_room_block",
            )

        blocked_audits = [
            row
            for row in self.repository.list_audit_events(room_id=restricted_room_id, limit=400)
            if row["event_type"] == "memory_correction_blocked"
        ]
        self.assertTrue(blocked_audits)
        blocked_payload = json.loads(blocked_audits[-1]["metadata_json"])
        self.assertEqual(blocked_payload["operation"], "supersede_event")
        self.assertEqual(blocked_payload["reason"], "cross_room_block")
        self.assertEqual(blocked_payload["superseded_by_id"], public_completed["id"])
        self.assertEqual(self._count_supersession_rows(room_id=restricted_room_id, old_event_id=restricted_started["id"]), 0)

    def test_detail_contract_stable_after_correction_and_replay(self) -> None:
        result = self._ingest_dataset(
            label="Detail Contract Stable",
            classification_level="personal",
            folder_name="detail_contract_stable",
            files={"note.txt": "alpha"},
        )
        room_id = "restricted-room"
        ingest_run_id = result["run"]["id"]
        episode_id = system_ingest_episode_id(room_id=room_id, ingest_run_id=ingest_run_id)
        started = self._event_by_type(room_id=room_id, event_type="ingest_started", ingest_run_id=ingest_run_id)
        completed = self._event_by_type(room_id=room_id, event_type="ingest_completed", ingest_run_id=ingest_run_id)

        self.memory_service.reject_episode(
            room_id=room_id,
            episode_id=episode_id,
            reason="contract_episode_reject",
        )
        self.memory_service.supersede_event(
            room_id=room_id,
            event_id=started["id"],
            superseded_by_event_id=completed["id"],
            reason="contract_supersede",
        )

        event_detail_before = memory_event_detail(
            event_id=started["id"],
            room_id=room_id,
            repository=self.repository,
        ).model_dump(mode="json")
        episode_detail_before = memory_episode_detail(
            episode_id=episode_id,
            room_id=room_id,
            repository=self.repository,
        ).model_dump(mode="json")

        self.memory_service.replay_memory_generation(room_id=room_id, ingest_run_id=ingest_run_id)
        self.memory_service.replay_memory_generation(room_id=room_id)

        event_detail_after = memory_event_detail(
            event_id=started["id"],
            room_id=room_id,
            repository=self.repository,
        ).model_dump(mode="json")
        episode_detail_after = memory_episode_detail(
            episode_id=episode_id,
            room_id=room_id,
            repository=self.repository,
        ).model_dump(mode="json")

        self.assertEqual(set(event_detail_before.keys()), set(event_detail_after.keys()))
        self.assertEqual(set(episode_detail_before.keys()), set(episode_detail_after.keys()))
        self.assertEqual(event_detail_before["status"], event_detail_after["status"])
        self.assertEqual(event_detail_before["correction_reason"], event_detail_after["correction_reason"])
        self.assertEqual(event_detail_before["superseded_by_id"], event_detail_after["superseded_by_id"])
        self.assertEqual(event_detail_before["source_lineage"], event_detail_after["source_lineage"])
        self.assertEqual(event_detail_before["seed_basis"], event_detail_after["seed_basis"])
        self.assertEqual(event_detail_before["provenance"], event_detail_after["provenance"])
        self.assertEqual(
            [
                (
                    item["sequence_no"],
                    item["inclusion_basis"],
                    item["episode"]["id"],
                    item["episode"]["status"],
                    item["episode"]["correction_reason"],
                    item["episode"]["corrected_at"],
                    item["episode"]["corrected_by_role"],
                )
                for item in event_detail_before["episode_memberships"]
            ],
            [
                (
                    item["sequence_no"],
                    item["inclusion_basis"],
                    item["episode"]["id"],
                    item["episode"]["status"],
                    item["episode"]["correction_reason"],
                    item["episode"]["corrected_at"],
                    item["episode"]["corrected_by_role"],
                )
                for item in event_detail_after["episode_memberships"]
            ],
        )
        self.assertEqual(event_detail_before["supersession_relationships"], event_detail_after["supersession_relationships"])
        self.assertEqual(episode_detail_before["status"], episode_detail_after["status"])
        self.assertEqual(episode_detail_before["correction_reason"], episode_detail_after["correction_reason"])
        self.assertEqual(episode_detail_before["source_lineage"], episode_detail_after["source_lineage"])
        self.assertEqual(episode_detail_before["membership_basis"], episode_detail_after["membership_basis"])
        self.assertEqual(episode_detail_before["provenance"], episode_detail_after["provenance"])
        self.assertEqual(episode_detail_before["linked_events"], episode_detail_after["linked_events"])

    def test_corrected_rows_remain_queryable_in_detail_reads(self) -> None:
        result = self._ingest_dataset(
            label="Queryable Corrected Rows",
            classification_level="personal",
            folder_name="queryable_corrected_rows",
            files={"note.txt": "alpha"},
        )
        room_id = "restricted-room"
        ingest_run_id = result["run"]["id"]
        episode_id = system_ingest_episode_id(room_id=room_id, ingest_run_id=ingest_run_id)
        requested = self._event_by_type(room_id=room_id, event_type="ingest_requested")
        started = self._event_by_type(room_id=room_id, event_type="ingest_started", ingest_run_id=ingest_run_id)
        completed = self._event_by_type(room_id=room_id, event_type="ingest_completed", ingest_run_id=ingest_run_id)

        self.memory_service.reject_event(
            room_id=room_id,
            event_id=requested["id"],
            reason="queryable_reject",
        )
        self.memory_service.reject_episode(
            room_id=room_id,
            episode_id=episode_id,
            reason="queryable_episode_reject",
        )
        self.memory_service.supersede_event(
            room_id=room_id,
            event_id=started["id"],
            superseded_by_event_id=completed["id"],
            reason="queryable_supersede",
        )

        rejected_event = self.memory_service.get_event_detail(room_id=room_id, event_id=requested["id"])
        superseded_event = self.memory_service.get_event_detail(room_id=room_id, event_id=started["id"])
        rejected_episode = self.memory_service.get_episode_detail(room_id=room_id, episode_id=episode_id)

        self.assertIsNotNone(rejected_event)
        self.assertIsNotNone(superseded_event)
        self.assertIsNotNone(rejected_episode)
        self.assertEqual(rejected_event["status"], "rejected")
        self.assertEqual(superseded_event["status"], "superseded")
        self.assertEqual(rejected_episode["status"], "rejected")

    def test_superseded_rows_retain_provenance_and_superseded_by_id(self) -> None:
        result = self._ingest_dataset(
            label="Superseded Provenance",
            classification_level="personal",
            folder_name="superseded_provenance",
            files={"note.txt": "alpha"},
        )
        room_id = "restricted-room"
        ingest_run_id = result["run"]["id"]
        started = self._event_by_type(room_id=room_id, event_type="ingest_started", ingest_run_id=ingest_run_id)
        completed = self._event_by_type(room_id=room_id, event_type="ingest_completed", ingest_run_id=ingest_run_id)

        before = self.memory_service.get_event_detail(room_id=room_id, event_id=started["id"])
        self.memory_service.supersede_event(
            room_id=room_id,
            event_id=started["id"],
            superseded_by_event_id=completed["id"],
            reason="retain_provenance",
        )
        after = self.memory_service.get_event_detail(room_id=room_id, event_id=started["id"])

        self.assertEqual(after["status"], "superseded")
        self.assertEqual(after["superseded_by_id"], completed["id"])
        self.assertEqual(before["source_lineage"], after["source_lineage"])
        self.assertEqual(before["provenance"], after["provenance"])
        self.assertTrue(after["provenance"])
        self.assertEqual(len(after["supersession_relationships"]), 1)

    def test_episode_membership_hydration_stays_consistent_after_event_correction_and_replay(self) -> None:
        result = self._ingest_dataset(
            label="Membership Hydration",
            classification_level="personal",
            folder_name="membership_hydration",
            files={"note.txt": "alpha"},
        )
        room_id = "restricted-room"
        ingest_run_id = result["run"]["id"]
        episode_id = system_ingest_episode_id(room_id=room_id, ingest_run_id=ingest_run_id)
        started = self._event_by_type(room_id=room_id, event_type="ingest_started", ingest_run_id=ingest_run_id)
        completed = self._event_by_type(room_id=room_id, event_type="ingest_completed", ingest_run_id=ingest_run_id)

        before_members = memory_episode_events(
            episode_id=episode_id,
            room_id=room_id,
            limit=100,
            offset=0,
            repository=self.repository,
        )
        before_structure = [(member.sequence_no, member.inclusion_basis, member.event.id) for member in before_members]

        self.memory_service.supersede_event(
            room_id=room_id,
            event_id=started["id"],
            superseded_by_event_id=completed["id"],
            reason="membership_supersede",
        )
        self.memory_service.replay_memory_generation(room_id=room_id, ingest_run_id=ingest_run_id)
        self.memory_service.replay_memory_generation(room_id=room_id)

        after_members = memory_episode_events(
            episode_id=episode_id,
            room_id=room_id,
            limit=100,
            offset=0,
            repository=self.repository,
        )
        after_structure = [(member.sequence_no, member.inclusion_basis, member.event.id) for member in after_members]
        after_statuses = {member.event.id: member.event.status for member in after_members}

        self.assertEqual(before_structure, after_structure)
        self.assertEqual(after_statuses[started["id"]], "superseded")
        self.assertEqual(after_statuses[completed["id"]], "active")

    def test_existing_db_bootstrap_tolerates_missing_correction_columns_and_supersession_table(self) -> None:
        legacy_path = self.root / "legacy_phase_2b2.sqlite"
        with closing(sqlite3.connect(legacy_path)) as conn:
            conn.executescript(
                """
                CREATE TABLE memory_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_id TEXT NOT NULL,
                    classification_level TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    source_table TEXT NOT NULL,
                    source_record_id TEXT NOT NULL,
                    dataset_id INTEGER,
                    asset_id INTEGER,
                    ingest_run_id INTEGER,
                    occurred_at TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    title TEXT NOT NULL,
                    evidence_text TEXT NOT NULL,
                    metadata_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(room_id, source_table, source_record_id, event_type)
                );

                CREATE TABLE memory_episodes (
                    id TEXT PRIMARY KEY,
                    room_id TEXT NOT NULL,
                    classification_level TEXT NOT NULL,
                    episode_type TEXT NOT NULL,
                    grouping_basis TEXT NOT NULL,
                    source_table TEXT NOT NULL,
                    source_record_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    start_at TEXT NOT NULL,
                    end_at TEXT NOT NULL,
                    metadata_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(room_id, source_table, source_record_id, episode_type)
                );
                """
            )
            timestamp = utc_now_iso()
            conn.execute(
                """
                INSERT INTO memory_events (
                    room_id, classification_level, event_type, source_table, source_record_id,
                    dataset_id, asset_id, ingest_run_id, occurred_at, recorded_at, title,
                    evidence_text, metadata_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "restricted-room",
                    "personal",
                    "ingest_completed",
                    "audit_events",
                    "123",
                    1,
                    None,
                    7,
                    timestamp,
                    timestamp,
                    "Legacy event",
                    "event_type=ingest_completed|room_id=restricted-room",
                    json.dumps({"legacy": True}),
                    timestamp,
                    timestamp,
                ),
            )
            conn.execute(
                """
                INSERT INTO memory_episodes (
                    id, room_id, classification_level, episode_type, grouping_basis,
                    source_table, source_record_id, title, summary, start_at, end_at,
                    metadata_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "episode:system_ingest_run:restricted-room:7",
                    "restricted-room",
                    "personal",
                    "system_ingest_run",
                    "7",
                    "ingest_runs",
                    "7",
                    "Legacy episode",
                    "ingest_run_id=7",
                    timestamp,
                    timestamp,
                    json.dumps({"legacy": True}),
                    timestamp,
                    timestamp,
                ),
            )
            conn.commit()

        legacy_repository = KloneRepository(legacy_path)
        legacy_repository.initialize()

        event_row = legacy_repository.get_memory_event(1, room_id="restricted-room")
        episode_row = legacy_repository.get_memory_episode(
            "episode:system_ingest_run:restricted-room:7",
            room_id="restricted-room",
        )
        with legacy_repository.connection() as conn:
            supersession_table = conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name = 'memory_event_supersessions'
                """
            ).fetchone()

        self.assertIsNotNone(supersession_table)
        self.assertEqual(event_row["status"], "active")
        self.assertEqual(event_row["evidence_text"], "event_type=ingest_completed|room_id=restricted-room")
        self.assertEqual(episode_row["status"], "active")
        self.assertEqual(episode_row["summary"], "ingest_run_id=7")

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

    def _event_by_type(
        self,
        *,
        room_id: str,
        event_type: str,
        ingest_run_id: int | None = None,
    ) -> dict:
        rows = self.repository.list_memory_events(
            room_id=room_id,
            limit=200,
            offset=0,
            ingest_run_id=ingest_run_id,
        )
        return next(row for row in rows if row["event_type"] == event_type)

    def _count_supersession_rows(
        self,
        *,
        room_id: str,
        old_event_id: int,
    ) -> int:
        with self.repository.connection() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS supersession_count
                FROM memory_event_supersessions
                WHERE room_id = ? AND old_event_id = ?
                """,
                (room_id, str(old_event_id)),
            ).fetchone()
            return int(row["supersession_count"])


if __name__ == "__main__":
    unittest.main()
