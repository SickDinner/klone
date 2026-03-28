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

from klone.api import memory_episode_provenance_detail, memory_event_provenance_detail  # noqa: E402
from klone.ingest import ingest_dataset  # noqa: E402
from klone.memory import MemoryService, system_ingest_episode_id  # noqa: E402
from klone.repository import KloneRepository  # noqa: E402
from klone.schemas import DatasetIngestRequest  # noqa: E402


class MemoryPhase2C1ProvenanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.repository = KloneRepository(self.root / "phase_2c1_provenance.sqlite")
        self.repository.initialize()
        self.memory_service = MemoryService(self.repository)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_event_provenance_read_is_room_scoped_deterministic_and_correction_visible(self) -> None:
        restricted_result = self._ingest_dataset(
            label="Restricted Provenance Event",
            classification_level="personal",
            folder_name="restricted_provenance_event",
            files={"note.txt": "alpha"},
        )
        self._ingest_dataset(
            label="Public Provenance Event",
            classification_level="public",
            folder_name="public_provenance_event",
            files={"note.txt": "beta"},
        )

        room_id = "restricted-room"
        public_room_id = "public-room"
        run_id = restricted_result["run"]["id"]
        run_events = self.repository.list_memory_events(
            room_id=room_id,
            limit=50,
            offset=0,
            ingest_run_id=run_id,
        )
        ingest_started = next(row for row in run_events if row["event_type"] == "ingest_started")
        ingest_completed = next(row for row in run_events if row["event_type"] == "ingest_completed")

        self.memory_service.supersede_event(
            room_id=room_id,
            event_id=ingest_started["id"],
            superseded_by_event_id=ingest_completed["id"],
            reason="provenance_supersede",
        )

        counts_before = self._read_counts()
        first = memory_event_provenance_detail(
            event_id=ingest_started["id"],
            room_id=room_id,
            repository=self.repository,
        )
        second = memory_event_provenance_detail(
            event_id=ingest_started["id"],
            room_id=room_id,
            repository=self.repository,
        )
        counts_after = self._read_counts()

        self.assertEqual(counts_before, counts_after)
        self.assertEqual(first.model_dump(mode="json"), second.model_dump(mode="json"))
        self.assertEqual(first.event.id, ingest_started["id"])
        self.assertEqual(first.event.room_id, room_id)
        self.assertEqual(first.event.status, "superseded")
        self.assertEqual(first.event.correction_reason, "provenance_supersede")
        self.assertEqual(first.event.superseded_by_id, ingest_completed["id"])
        self.assertEqual(
            [row.id for row in first.provenance],
            [
                row["id"]
                for row in self.repository.list_memory_provenance(
                    room_id=room_id,
                    owner_type="event",
                    owner_id=str(ingest_started["id"]),
                )
            ],
        )
        self.assertTrue(first.source_lineage)
        self.assertTrue(first.seed_basis)
        self.assertTrue(all(row.provenance_type == "source_lineage" for row in first.source_lineage))
        self.assertTrue(all(row.provenance_type == "seed_basis" for row in first.seed_basis))
        self.assertEqual(first.provenance_summary.total_count, len(first.provenance))
        self.assertGreater(first.provenance_summary.source_lineage_count, 0)

        with self.assertRaises(HTTPException) as cross_room_error:
            memory_event_provenance_detail(
                event_id=ingest_started["id"],
                room_id=public_room_id,
                repository=self.repository,
            )
        self.assertEqual(cross_room_error.exception.status_code, 404)

    def test_episode_provenance_read_is_room_scoped_deterministic_and_membership_linked(self) -> None:
        restricted_result = self._ingest_dataset(
            label="Restricted Provenance Episode",
            classification_level="personal",
            folder_name="restricted_provenance_episode",
            files={"note.txt": "alpha"},
        )
        self._ingest_dataset(
            label="Public Provenance Episode",
            classification_level="public",
            folder_name="public_provenance_episode",
            files={"note.txt": "beta"},
        )

        room_id = "restricted-room"
        public_room_id = "public-room"
        run_id = restricted_result["run"]["id"]
        episode_id = system_ingest_episode_id(room_id=room_id, ingest_run_id=run_id)

        self.memory_service.reject_episode(
            room_id=room_id,
            episode_id=episode_id,
            reason="provenance_episode_reject",
        )

        counts_before = self._read_counts()
        first = memory_episode_provenance_detail(
            episode_id=episode_id,
            room_id=room_id,
            repository=self.repository,
        )
        second = memory_episode_provenance_detail(
            episode_id=episode_id,
            room_id=room_id,
            repository=self.repository,
        )
        counts_after = self._read_counts()

        self.assertEqual(counts_before, counts_after)
        self.assertEqual(first.model_dump(mode="json"), second.model_dump(mode="json"))
        self.assertEqual(first.episode.id, episode_id)
        self.assertEqual(first.episode.room_id, room_id)
        self.assertEqual(first.episode.status, "rejected")
        self.assertEqual(first.episode.correction_reason, "provenance_episode_reject")
        self.assertEqual(
            [row.id for row in first.provenance],
            [
                row["id"]
                for row in self.repository.list_memory_provenance(
                    room_id=room_id,
                    owner_type="episode",
                    owner_id=episode_id,
                )
            ],
        )
        self.assertTrue(first.source_lineage)
        self.assertTrue(first.seed_basis)
        self.assertTrue(first.membership_basis)
        self.assertTrue(all(row.provenance_type == "source_lineage" for row in first.source_lineage))
        self.assertTrue(all(row.provenance_type == "seed_basis" for row in first.seed_basis))
        self.assertTrue(all(row.provenance_type == "membership_basis" for row in first.membership_basis))
        self.assertEqual(first.provenance_summary.total_count, len(first.provenance))
        self.assertEqual(first.provenance_summary.membership_basis_count, len(first.membership_basis))

        with self.assertRaises(HTTPException) as cross_room_error:
            memory_episode_provenance_detail(
                episode_id=episode_id,
                room_id=public_room_id,
                repository=self.repository,
            )
        self.assertEqual(cross_room_error.exception.status_code, 404)

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

    def _read_counts(self) -> dict[str, int]:
        with self.repository.connection() as conn:
            return {
                "events": int(conn.execute("SELECT COUNT(*) FROM memory_events").fetchone()[0]),
                "episodes": int(conn.execute("SELECT COUNT(*) FROM memory_episodes").fetchone()[0]),
                "provenance": int(conn.execute("SELECT COUNT(*) FROM memory_provenance").fetchone()[0]),
                "audit": int(conn.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]),
                "internal_runs": int(conn.execute("SELECT COUNT(*) FROM internal_runs").fetchone()[0]),
            }


if __name__ == "__main__":
    unittest.main()
