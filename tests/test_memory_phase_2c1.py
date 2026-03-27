from __future__ import annotations

import sys
from pathlib import Path
import tempfile
import unittest

from fastapi import HTTPException


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from klone.api import memory_episode_detail, memory_episode_events, memory_episodes, memory_event_detail, memory_events  # noqa: E402
from klone.ingest import ingest_dataset  # noqa: E402
from klone.memory import MemoryService, system_ingest_episode_id  # noqa: E402
from klone.repository import KloneRepository  # noqa: E402
from klone.schemas import DatasetIngestRequest  # noqa: E402


class MemoryPhase2C1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.repository = KloneRepository(self.root / "phase_2c1.sqlite")
        self.repository.initialize()
        self.memory_service = MemoryService(self.repository)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_status_filters_include_corrected_and_ingest_run_scope(self) -> None:
        first_result = self._ingest_dataset(
            label="Restricted One",
            classification_level="personal",
            folder_name="restricted_one",
            files={"a.txt": "one"},
        )
        second_result = self._ingest_dataset(
            label="Restricted Two",
            classification_level="personal",
            folder_name="restricted_two",
            files={"b.txt": "two"},
        )
        room_id = "restricted-room"
        first_run_id = first_result["run"]["id"]
        second_run_id = second_result["run"]["id"]
        first_episode_id = system_ingest_episode_id(room_id=room_id, ingest_run_id=first_run_id)

        first_run_events = self.repository.list_memory_events(
            room_id=room_id,
            limit=50,
            offset=0,
            ingest_run_id=first_run_id,
        )
        ingest_requested = next(
            row
            for row in self.repository.list_memory_events(room_id=room_id, limit=100, offset=0)
            if row["event_type"] == "ingest_requested"
        )
        ingest_started = next(row for row in first_run_events if row["event_type"] == "ingest_started")
        ingest_completed = next(row for row in first_run_events if row["event_type"] == "ingest_completed")

        self.memory_service.reject_event(
            room_id=room_id,
            event_id=ingest_requested["id"],
            reason="operator_reject",
        )
        self.memory_service.reject_episode(
            room_id=room_id,
            episode_id=first_episode_id,
            reason="operator_episode_reject",
        )
        self.memory_service.supersede_event(
            room_id=room_id,
            event_id=ingest_started["id"],
            superseded_by_event_id=ingest_completed["id"],
            reason="operator_supersede",
        )

        active_events = memory_events(
            room_id=room_id,
            limit=100,
            offset=0,
            status=None,
            event_type=None,
            ingest_run_id=None,
            include_corrected=False,
            repository=self.repository,
        )
        rejected_events = memory_events(
            room_id=room_id,
            limit=100,
            offset=0,
            status="rejected",
            event_type=None,
            ingest_run_id=None,
            include_corrected=True,
            repository=self.repository,
        )
        superseded_events = memory_events(
            room_id=room_id,
            limit=100,
            offset=0,
            status="superseded",
            event_type=None,
            ingest_run_id=None,
            include_corrected=True,
            repository=self.repository,
        )
        completed_events = memory_events(
            room_id=room_id,
            limit=100,
            offset=0,
            status=None,
            event_type="ingest_completed",
            ingest_run_id=None,
            include_corrected=True,
            repository=self.repository,
        )
        run_scoped_events = memory_events(
            room_id=room_id,
            limit=100,
            offset=0,
            status=None,
            event_type=None,
            ingest_run_id=first_run_id,
            include_corrected=True,
            repository=self.repository,
        )

        active_episodes = memory_episodes(
            room_id=room_id,
            limit=100,
            offset=0,
            status=None,
            episode_type=None,
            ingest_run_id=None,
            include_corrected=False,
            repository=self.repository,
        )
        rejected_episodes = memory_episodes(
            room_id=room_id,
            limit=100,
            offset=0,
            status="rejected",
            episode_type=None,
            ingest_run_id=None,
            include_corrected=True,
            repository=self.repository,
        )
        second_run_episode = memory_episodes(
            room_id=room_id,
            limit=100,
            offset=0,
            status=None,
            episode_type=None,
            ingest_run_id=second_run_id,
            include_corrected=True,
            repository=self.repository,
        )
        episode_order_once = [
            row.id
            for row in memory_episodes(
                room_id=room_id,
                limit=100,
                offset=0,
                status=None,
                episode_type=None,
                ingest_run_id=None,
                include_corrected=True,
                repository=self.repository,
            )
        ]
        episode_order_twice = [
            row.id
            for row in memory_episodes(
                room_id=room_id,
                limit=100,
                offset=0,
                status=None,
                episode_type=None,
                ingest_run_id=None,
                include_corrected=True,
                repository=self.repository,
            )
        ]

        self.assertTrue(all(row.status == "active" for row in active_events))
        self.assertEqual([row.id for row in rejected_events], [ingest_requested["id"]])
        self.assertEqual([row.id for row in superseded_events], [ingest_started["id"]])
        self.assertTrue(all(row.event_type == "ingest_completed" for row in completed_events))
        self.assertTrue(all(row.ingest_run_id == first_run_id for row in run_scoped_events))
        self.assertTrue(all(row.status == "active" for row in active_episodes))
        self.assertEqual([row.id for row in rejected_episodes], [first_episode_id])
        self.assertEqual([row.id for row in second_run_episode], [
            system_ingest_episode_id(room_id=room_id, ingest_run_id=second_run_id)
        ])
        self.assertEqual(episode_order_once, episode_order_twice)

    def test_detail_traversal_is_supersession_and_provenance_aware(self) -> None:
        result = self._ingest_dataset(
            label="Restricted Detail",
            classification_level="personal",
            folder_name="restricted_detail",
            files={"a.txt": "one"},
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

        self.memory_service.supersede_event(
            room_id=room_id,
            event_id=ingest_started["id"],
            superseded_by_event_id=ingest_completed["id"],
            reason="operator_supersede",
        )

        event_detail = memory_event_detail(
            event_id=ingest_started["id"],
            room_id=room_id,
            repository=self.repository,
        )
        replacement_detail = memory_event_detail(
            event_id=ingest_completed["id"],
            room_id=room_id,
            repository=self.repository,
        )
        episode_detail = memory_episode_detail(
            episode_id=episode_id,
            room_id=room_id,
            repository=self.repository,
        )

        self.assertEqual(event_detail.status, "superseded")
        self.assertEqual(event_detail.provenance_summary.total_count, len(event_detail.provenance))
        self.assertGreater(event_detail.provenance_summary.source_lineage_count, 0)
        self.assertGreaterEqual(len(event_detail.episode_memberships), 1)
        self.assertEqual(event_detail.episode_memberships[0].episode.id, episode_id)
        self.assertEqual(event_detail.episode_memberships[0].episode.status, "active")
        self.assertEqual(len(event_detail.supersession_relationships), 1)
        self.assertEqual(event_detail.supersession_relationships[0].event_role, "old_event")
        self.assertEqual(event_detail.supersession_relationships[0].new_event_id, str(ingest_completed["id"]))

        self.assertEqual(len(replacement_detail.supersession_relationships), 1)
        self.assertEqual(replacement_detail.supersession_relationships[0].event_role, "new_event")
        self.assertEqual(
            replacement_detail.supersession_relationships[0].old_event_id,
            str(ingest_started["id"]),
        )

        self.assertEqual(episode_detail.provenance_summary.total_count, len(episode_detail.provenance))
        self.assertGreater(episode_detail.provenance_summary.source_lineage_count, 0)
        self.assertGreater(episode_detail.provenance_summary.membership_basis_count, 0)
        self.assertGreaterEqual(len(episode_detail.linked_events), 1)

    def test_query_results_expose_provenance_summary(self) -> None:
        result = self._ingest_dataset(
            label="Query Provenance Summary",
            classification_level="personal",
            folder_name="query_provenance_summary",
            files={"note.txt": "alpha"},
        )

        room_id = "restricted-room"
        run_id = result["run"]["id"]
        episode_id = system_ingest_episode_id(room_id=room_id, ingest_run_id=run_id)

        event_rows = memory_events(
            room_id=room_id,
            repository=self.repository,
            limit=50,
            offset=0,
            status=None,
            event_type=None,
            ingest_run_id=run_id,
            include_corrected=True,
        )
        self.assertTrue(event_rows)
        started_event = next(row for row in event_rows if row.event_type == "ingest_started")
        self.assertIsNotNone(started_event.provenance_summary)
        self.assertGreater(started_event.provenance_summary.total_count, 0)
        self.assertGreater(started_event.provenance_summary.source_lineage_count, 0)

        episode_rows = memory_episodes(
            room_id=room_id,
            repository=self.repository,
            limit=50,
            offset=0,
            status=None,
            episode_type=None,
            ingest_run_id=run_id,
            include_corrected=True,
        )
        self.assertTrue(episode_rows)
        episode_row = next(row for row in episode_rows if row.id == episode_id)
        self.assertIsNotNone(episode_row.provenance_summary)
        self.assertGreater(episode_row.provenance_summary.total_count, 0)
        self.assertGreater(episode_row.provenance_summary.source_lineage_count, 0)

    def test_room_isolation_for_queries_and_traversal(self) -> None:
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
        restricted_started = next(row for row in restricted_events if row["event_type"] == "ingest_started")
        restricted_completed = next(row for row in restricted_events if row["event_type"] == "ingest_completed")

        self.memory_service.reject_episode(
            room_id=restricted_room_id,
            episode_id=restricted_episode_id,
            reason="episode_reject",
        )
        self.memory_service.supersede_event(
            room_id=restricted_room_id,
            event_id=restricted_started["id"],
            superseded_by_event_id=restricted_completed["id"],
            reason="operator_supersede",
        )

        public_rejected_events = memory_events(
            room_id=public_room_id,
            limit=100,
            offset=0,
            status="rejected",
            event_type=None,
            ingest_run_id=None,
            include_corrected=True,
            repository=self.repository,
        )
        public_active_episodes = memory_episodes(
            room_id=public_room_id,
            limit=100,
            offset=0,
            status=None,
            episode_type=None,
            ingest_run_id=None,
            include_corrected=False,
            repository=self.repository,
        )
        restricted_detail = memory_event_detail(
            event_id=restricted_started["id"],
            room_id=restricted_room_id,
            repository=self.repository,
        )

        self.assertEqual(public_rejected_events, [])
        self.assertTrue(all(row.status == "active" for row in public_active_episodes))
        self.assertIsNone(
            self.memory_service.get_event_detail(
                room_id=public_room_id,
                event_id=restricted_started["id"],
            )
        )
        self.assertEqual(restricted_detail.status, "superseded")
        self.assertEqual(len(restricted_detail.supersession_relationships), 1)

    def test_episode_query_filters_order_and_pagination_are_room_scoped(self) -> None:
        restricted_one = self._ingest_dataset(
            label="Restricted Episodes One",
            classification_level="personal",
            folder_name="restricted_episodes_one",
            files={"one.txt": "alpha"},
        )
        restricted_two = self._ingest_dataset(
            label="Restricted Episodes Two",
            classification_level="personal",
            folder_name="restricted_episodes_two",
            files={"two.txt": "beta"},
        )
        self._ingest_dataset(
            label="Public Episodes",
            classification_level="public",
            folder_name="public_episodes",
            files={"three.txt": "gamma"},
        )

        room_id = "restricted-room"
        first_episode_id = system_ingest_episode_id(room_id=room_id, ingest_run_id=restricted_one["run"]["id"])
        second_episode_id = system_ingest_episode_id(room_id=room_id, ingest_run_id=restricted_two["run"]["id"])

        self.memory_service.reject_episode(
            room_id=room_id,
            episode_id=first_episode_id,
            reason="episode_filter_reject",
        )

        active_only = memory_episodes(
            room_id=room_id,
            limit=50,
            offset=0,
            status=None,
            episode_type=None,
            ingest_run_id=None,
            include_corrected=False,
            repository=self.repository,
        )
        rejected_only = memory_episodes(
            room_id=room_id,
            limit=50,
            offset=0,
            status="rejected",
            episode_type=None,
            ingest_run_id=None,
            include_corrected=True,
            repository=self.repository,
        )
        first_page = memory_episodes(
            room_id=room_id,
            limit=1,
            offset=0,
            status=None,
            episode_type=None,
            ingest_run_id=None,
            include_corrected=True,
            repository=self.repository,
        )
        second_page = memory_episodes(
            room_id=room_id,
            limit=1,
            offset=1,
            status=None,
            episode_type=None,
            ingest_run_id=None,
            include_corrected=True,
            repository=self.repository,
        )
        ordered_once = [
            row.id
            for row in memory_episodes(
                room_id=room_id,
                limit=50,
                offset=0,
                status=None,
                episode_type=None,
                ingest_run_id=None,
                include_corrected=True,
                repository=self.repository,
            )
        ]
        ordered_twice = [
            row.id
            for row in memory_episodes(
                room_id=room_id,
                limit=50,
                offset=0,
                status=None,
                episode_type=None,
                ingest_run_id=None,
                include_corrected=True,
                repository=self.repository,
            )
        ]
        run_scoped = memory_episodes(
            room_id=room_id,
            limit=50,
            offset=0,
            status=None,
            episode_type=None,
            ingest_run_id=restricted_one["run"]["id"],
            include_corrected=True,
            repository=self.repository,
        )

        self.assertEqual([row.id for row in active_only], [second_episode_id])
        self.assertEqual([row.id for row in rejected_only], [first_episode_id])
        self.assertEqual(ordered_once, ordered_twice)
        self.assertEqual([row.id for row in first_page + second_page], ordered_once[:2])
        self.assertEqual([row.id for row in run_scoped], [first_episode_id])

        public_rows = memory_episodes(
            room_id="public-room",
            limit=50,
            offset=0,
            status=None,
            episode_type=None,
            ingest_run_id=None,
            include_corrected=True,
            repository=self.repository,
        )
        self.assertTrue(all(row.room_id == "public-room" for row in public_rows))
        self.assertNotIn(first_episode_id, [row.id for row in public_rows])
        self.assertNotIn(second_episode_id, [row.id for row in public_rows])

    def test_episode_event_traversal_is_read_only_correction_aware_and_room_scoped(self) -> None:
        restricted_result = self._ingest_dataset(
            label="Restricted Traversal",
            classification_level="personal",
            folder_name="restricted_traversal",
            files={"note.txt": "alpha"},
        )
        public_result = self._ingest_dataset(
            label="Public Traversal",
            classification_level="public",
            folder_name="public_traversal",
            files={"note.txt": "beta"},
        )

        restricted_room_id = "restricted-room"
        public_room_id = "public-room"
        restricted_run_id = restricted_result["run"]["id"]
        restricted_episode_id = system_ingest_episode_id(
            room_id=restricted_room_id,
            ingest_run_id=restricted_run_id,
        )
        public_episode_id = system_ingest_episode_id(
            room_id=public_room_id,
            ingest_run_id=public_result["run"]["id"],
        )

        restricted_events = self.repository.list_memory_events(
            room_id=restricted_room_id,
            limit=50,
            offset=0,
            ingest_run_id=restricted_run_id,
        )
        ingest_started = next(row for row in restricted_events if row["event_type"] == "ingest_started")
        ingest_completed = next(row for row in restricted_events if row["event_type"] == "ingest_completed")

        self.memory_service.reject_episode(
            room_id=restricted_room_id,
            episode_id=restricted_episode_id,
            reason="episode_traversal_reject",
        )
        self.memory_service.supersede_event(
            room_id=restricted_room_id,
            event_id=ingest_started["id"],
            superseded_by_event_id=ingest_completed["id"],
            reason="episode_traversal_supersede",
        )

        detail = memory_episode_detail(
            episode_id=restricted_episode_id,
            room_id=restricted_room_id,
            repository=self.repository,
        )
        members = memory_episode_events(
            episode_id=restricted_episode_id,
            room_id=restricted_room_id,
            limit=50,
            offset=0,
            repository=self.repository,
        )
        first_page = memory_episode_events(
            episode_id=restricted_episode_id,
            room_id=restricted_room_id,
            limit=1,
            offset=0,
            repository=self.repository,
        )
        second_page = memory_episode_events(
            episode_id=restricted_episode_id,
            room_id=restricted_room_id,
            limit=1,
            offset=1,
            repository=self.repository,
        )

        self.assertEqual(detail.status, "rejected")
        self.assertEqual(detail.correction_reason, "episode_traversal_reject")
        self.assertEqual([item.sequence_no for item in members], [1, 2])
        self.assertEqual(
            [(item.sequence_no, item.inclusion_basis, item.event.id) for item in first_page + second_page],
            [(item.sequence_no, item.inclusion_basis, item.event.id) for item in members[:2]],
        )
        self.assertEqual(members[0].event.id, ingest_started["id"])
        self.assertEqual(members[0].event.status, "superseded")
        self.assertEqual(members[0].event.superseded_by_id, ingest_completed["id"])
        self.assertEqual(members[0].event.correction_reason, "episode_traversal_supersede")
        self.assertEqual(members[1].event.id, ingest_completed["id"])
        self.assertEqual(members[1].event.status, "active")

        with self.assertRaises(HTTPException) as public_read_error:
            memory_episode_events(
                episode_id=restricted_episode_id,
                room_id=public_room_id,
                limit=50,
                offset=0,
                repository=self.repository,
            )
        self.assertEqual(public_read_error.exception.status_code, 404)

        public_detail = memory_episode_detail(
            episode_id=public_episode_id,
            room_id=public_room_id,
            repository=self.repository,
        )
        self.assertEqual(public_detail.status, "active")

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
