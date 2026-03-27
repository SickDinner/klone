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
from klone.schemas import DatasetIngestRequest  # noqa: E402


class MemoryPhase2B2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.repository = KloneRepository(self.root / "phase_2b2.sqlite")
        self.repository.initialize()
        self.memory_service = MemoryService(self.repository)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_provenance_replay_and_detail_exactness(self) -> None:
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
        ingest_completed = next(row for row in event_rows if row["event_type"] == "ingest_completed")
        before_counts = self._room_counts(room_id)
        before_event_evidence = ingest_completed["evidence_text"]
        before_event_detail = self.memory_service.get_event_detail(
            room_id=room_id,
            event_id=ingest_completed["id"],
        )
        before_episode_detail = self.memory_service.get_episode_detail(
            room_id=room_id,
            episode_id=episode_id,
        )

        self.assertIsNotNone(before_event_detail)
        self.assertIsNotNone(before_episode_detail)
        self.assertTrue(before_event_detail["source_lineage"])
        self.assertTrue(before_event_detail["seed_basis"])
        self.assertTrue(before_event_detail["provenance"])
        self.assertTrue(before_event_detail["linked_entities"])
        self.assertTrue(before_episode_detail["source_lineage"])
        self.assertTrue(before_episode_detail["seed_basis"])
        self.assertTrue(before_episode_detail["membership_basis"])
        self.assertTrue(before_episode_detail["provenance"])
        self.assertTrue(before_episode_detail["linked_events"])

        replay_result = self.memory_service.replay_memory_generation(
            room_id=room_id,
            ingest_run_id=ingest_run_id,
        )

        after_counts = self._room_counts(room_id)
        after_event = self.repository.get_memory_event(ingest_completed["id"], room_id=room_id)
        after_event_detail = self.memory_service.get_event_detail(
            room_id=room_id,
            event_id=ingest_completed["id"],
        )
        after_episode_detail = self.memory_service.get_episode_detail(
            room_id=room_id,
            episode_id=episode_id,
        )

        self.assertEqual(before_counts, after_counts)
        self.assertEqual(before_event_evidence, after_event["evidence_text"])
        self.assertEqual(before_event_detail["source_lineage"], after_event_detail["source_lineage"])
        self.assertEqual(before_event_detail["seed_basis"], after_event_detail["seed_basis"])
        self.assertEqual(before_episode_detail["source_lineage"], after_episode_detail["source_lineage"])
        self.assertEqual(before_episode_detail["membership_basis"], after_episode_detail["membership_basis"])
        self.assertEqual(episode_id, system_ingest_episode_id(room_id=room_id, ingest_run_id=ingest_run_id))
        self.assertEqual(replay_result.room_id, room_id)
        self.assertEqual(replay_result.ingest_run_id, ingest_run_id)
        self.assertGreaterEqual(replay_result.events_upserted, 1)
        self.assertGreaterEqual(replay_result.episodes_upserted, 1)
        self.assertGreaterEqual(replay_result.provenance_upserted, 1)

        audit_events = self.repository.list_audit_events(room_id=room_id, limit=200)
        replay_types = [row["event_type"] for row in audit_events]
        self.assertIn("memory_replay_started", replay_types)
        self.assertIn("memory_replay_completed", replay_types)

    def test_room_isolation_and_scoped_replay(self) -> None:
        restricted_one = self._ingest_dataset(
            label="Restricted One",
            classification_level="personal",
            folder_name="restricted_one",
            files={"a.txt": "one"},
        )
        restricted_two = self._ingest_dataset(
            label="Restricted Two",
            classification_level="personal",
            folder_name="restricted_two",
            files={"b.txt": "two"},
        )
        public_result = self._ingest_dataset(
            label="Public One",
            classification_level="public",
            folder_name="public_one",
            files={"c.txt": "three"},
        )

        restricted_room_id = "restricted-room"
        public_room_id = "public-room"
        restricted_replay_run_id = restricted_one["run"]["id"]
        unrelated_episode_id = system_ingest_episode_id(
            room_id=restricted_room_id,
            ingest_run_id=restricted_two["run"]["id"],
        )
        public_episode_id = system_ingest_episode_id(
            room_id=public_room_id,
            ingest_run_id=public_result["run"]["id"],
        )

        before_unrelated_episode = self.memory_service.get_episode_detail(
            room_id=restricted_room_id,
            episode_id=unrelated_episode_id,
        )
        before_public_counts = self._room_counts(public_room_id)

        restricted_event_id = self.repository.list_memory_events(
            room_id=restricted_room_id,
            limit=1,
            offset=0,
        )[0]["id"]
        self.assertIsNone(
            self.memory_service.get_event_detail(
                room_id=public_room_id,
                event_id=restricted_event_id,
            )
        )
        self.assertIsNone(
            self.memory_service.get_episode_detail(
                room_id=public_room_id,
                episode_id=system_ingest_episode_id(
                    room_id=restricted_room_id,
                    ingest_run_id=restricted_replay_run_id,
                ),
            )
        )

        replay_result = self.memory_service.replay_memory_generation(
            room_id=restricted_room_id,
            ingest_run_id=restricted_replay_run_id,
        )

        after_unrelated_episode = self.memory_service.get_episode_detail(
            room_id=restricted_room_id,
            episode_id=unrelated_episode_id,
        )
        after_public_counts = self._room_counts(public_room_id)
        public_episode_detail = self.memory_service.get_episode_detail(
            room_id=public_room_id,
            episode_id=public_episode_id,
        )

        self.assertEqual(before_unrelated_episode["source_lineage"], after_unrelated_episode["source_lineage"])
        self.assertEqual(before_unrelated_episode["membership_basis"], after_unrelated_episode["membership_basis"])
        self.assertEqual(before_unrelated_episode["linked_events"], after_unrelated_episode["linked_events"])
        self.assertEqual(before_public_counts, after_public_counts)
        self.assertIsNotNone(public_episode_detail)
        self.assertEqual(replay_result.room_id, restricted_room_id)
        self.assertEqual(replay_result.ingest_run_id, restricted_replay_run_id)

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

    def _room_counts(self, room_id: str) -> dict[str, int]:
        with self.repository.connection() as conn:
            return {
                "events": int(
                    conn.execute(
                        "SELECT COUNT(*) FROM memory_events WHERE room_id = ?",
                        (room_id,),
                    ).fetchone()[0]
                ),
                "entities": int(
                    conn.execute(
                        "SELECT COUNT(*) FROM memory_entities WHERE room_id = ?",
                        (room_id,),
                    ).fetchone()[0]
                ),
                "episodes": int(
                    conn.execute(
                        "SELECT COUNT(*) FROM memory_episodes WHERE room_id = ?",
                        (room_id,),
                    ).fetchone()[0]
                ),
                "event_entity_links": int(
                    conn.execute(
                        """
                        SELECT COUNT(*)
                        FROM memory_event_entities mee
                        JOIN memory_events me ON me.id = mee.event_id
                        WHERE me.room_id = ?
                        """,
                        (room_id,),
                    ).fetchone()[0]
                ),
                "episode_event_links": int(
                    conn.execute(
                        """
                        SELECT COUNT(*)
                        FROM memory_episode_events mee
                        JOIN memory_episodes me ON me.id = mee.episode_id
                        WHERE me.room_id = ?
                        """,
                        (room_id,),
                    ).fetchone()[0]
                ),
                "provenance": int(
                    conn.execute(
                        "SELECT COUNT(*) FROM memory_provenance WHERE room_id = ?",
                        (room_id,),
                    ).fetchone()[0]
                ),
            }


if __name__ == "__main__":
    unittest.main()
