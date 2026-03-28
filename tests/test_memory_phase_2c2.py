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
from klone.schemas import DatasetIngestRequest, MemoryContextPackageRecord  # noqa: E402


class MemoryPhase2C2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.repository = KloneRepository(self.root / "phase_2c2.sqlite")
        self.repository.initialize()
        self.memory_service = MemoryService(self.repository)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_episode_context_package_is_deterministic_correction_aware_and_source_linked(self) -> None:
        result = self._ingest_dataset(
            label="Episode Context",
            classification_level="personal",
            folder_name="episode_context",
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
            reason="episode_context_reject",
        )
        self.memory_service.supersede_event(
            room_id=room_id,
            event_id=ingest_started["id"],
            superseded_by_event_id=ingest_completed["id"],
            reason="episode_context_supersede",
        )

        package_once = self.memory_service.assemble_context_package(
            room_id=room_id,
            episode_id=episode_id,
        )
        package_twice = self.memory_service.assemble_context_package(
            room_id=room_id,
            episode_id=episode_id,
        )

        self.assertIsInstance(package_once, MemoryContextPackageRecord)
        self.assertEqual(package_once.model_dump(), package_twice.model_dump())
        self.assertEqual(package_once.room_id, room_id)
        self.assertEqual(package_once.query_scope.scope_kind, "episode_detail")
        self.assertEqual(package_once.query_scope.primary_episode_id, episode_id)
        self.assertEqual([item.id for item in package_once.included_episodes], [episode_id])
        self.assertEqual(
            [item.id for item in package_once.included_events],
            [ingest_started["id"], ingest_completed["id"]],
        )
        self.assertEqual(package_once.included_episodes[0].status, "rejected")
        self.assertEqual(package_once.included_events[0].status, "superseded")
        self.assertEqual(package_once.included_events[0].superseded_by_id, ingest_completed["id"])
        self.assertEqual(package_once.correction_summary.corrected_episode_ids, [episode_id])
        self.assertEqual(package_once.correction_summary.rejected_episode_ids, [episode_id])
        self.assertEqual(package_once.correction_summary.superseded_event_ids, [ingest_started["id"]])
        self.assertEqual(
            [
                (item.old_event_id, item.new_event_id)
                for item in package_once.correction_summary.supersession_links
            ],
            [(str(ingest_started["id"]), str(ingest_completed["id"]))],
        )

        provenance_ids, provenance_refs = self._package_provenance_snapshot(package_once)
        self.assertEqual(package_once.provenance_summary.total_count, len(provenance_ids))
        self.assertEqual(package_once.provenance_summary.source_refs, provenance_refs)
        self.assertEqual(package_once.warnings, [])

    def test_event_context_package_is_room_scoped_and_includes_linked_episode_details(self) -> None:
        restricted_result = self._ingest_dataset(
            label="Restricted Event Context",
            classification_level="personal",
            folder_name="restricted_event_context",
            files={"note.txt": "alpha"},
        )
        self._ingest_dataset(
            label="Public Event Context",
            classification_level="public",
            folder_name="public_event_context",
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

        self.memory_service.reject_episode(
            room_id=restricted_room_id,
            episode_id=restricted_episode_id,
            reason="event_context_episode_reject",
        )
        self.memory_service.supersede_event(
            room_id=restricted_room_id,
            event_id=ingest_started["id"],
            superseded_by_event_id=ingest_completed["id"],
            reason="event_context_supersede",
        )

        package = self.memory_service.assemble_context_package(
            room_id=restricted_room_id,
            event_id=ingest_started["id"],
        )

        self.assertEqual(package.query_scope.scope_kind, "event_detail")
        self.assertEqual(package.query_scope.primary_event_id, ingest_started["id"])
        self.assertEqual([item.id for item in package.included_events], [ingest_started["id"]])
        self.assertEqual([item.id for item in package.included_episodes], [restricted_episode_id])
        self.assertEqual(package.included_events[0].status, "superseded")
        self.assertEqual(package.included_episodes[0].status, "rejected")
        self.assertEqual(package.correction_summary.corrected_event_ids, [ingest_started["id"]])
        self.assertEqual(package.correction_summary.rejected_episode_ids, [restricted_episode_id])
        self.assertEqual(package.correction_summary.superseded_event_ids, [ingest_started["id"]])
        self.assertEqual(package.warnings, [])

        with self.assertRaises(ValueError):
            self.memory_service.assemble_context_package(
                room_id=public_room_id,
                event_id=ingest_started["id"],
            )

    def _package_provenance_snapshot(
        self,
        package: MemoryContextPackageRecord,
    ) -> tuple[list[int], list[str]]:
        provenance_by_id: dict[int, str] = {}
        for event in package.included_events:
            for row in event.provenance:
                provenance_by_id[row.id] = f"{row.source_table}:{row.source_record_id}"
        for episode in package.included_episodes:
            for row in episode.provenance:
                provenance_by_id[row.id] = f"{row.source_table}:{row.source_record_id}"
        return sorted(provenance_by_id), sorted(set(provenance_by_id.values()))

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
