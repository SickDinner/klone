from __future__ import annotations

import asyncio
import sys
from pathlib import Path
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from klone.api import (  # noqa: E402
    simulation_hybrid_board,
    simulation_hybrid_board_square_detail,
    simulation_world_memory,
    simulation_world_memory_cluster_detail,
    simulation_world_memory_node_detail,
)
from klone.config import Settings  # noqa: E402
from klone.ingest import ingest_dataset  # noqa: E402
from klone.main import create_app  # noqa: E402
from klone.schemas import DatasetIngestRequest  # noqa: E402


class SimulationPhaseS11Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_hybrid_board_is_read_only_64_square_and_deterministic(self) -> None:
        app = create_app(self._settings_for("simulation_board.sqlite"))
        observed = asyncio.run(self._collect_board_payloads(app))

        aggregate_board = observed["aggregate"]
        restricted_board = observed["restricted"]
        square_detail = observed["square_detail"]
        linked_square_detail = observed["linked_square_detail"]
        world_memory = observed["world_memory"]
        cluster_detail = observed["cluster_detail"]
        node_detail = observed["node_detail"]
        world_memory_repeat = observed["world_memory_repeat"]

        self.assertTrue(aggregate_board["read_only"])
        self.assertEqual(aggregate_board["square_count"], 64)
        self.assertEqual(len(aggregate_board["row_axes"]), 8)
        self.assertEqual(len(aggregate_board["column_axes"]), 8)
        self.assertEqual(len(aggregate_board["squares"]), 64)
        self.assertEqual(
            len({square["square_id"] for square in aggregate_board["squares"]}),
            64,
        )
        self.assertGreater(aggregate_board["source_totals"]["audit_events"], 0)
        self.assertGreater(aggregate_board["source_totals"]["memory_events"], 0)
        self.assertGreater(aggregate_board["source_totals"]["memory_episodes"], 0)
        self.assertTrue(any(square["activity_score"] > 0 for square in aggregate_board["squares"]))
        self.assertIn("restricted-room", aggregate_board["resolved_room_ids"])
        self.assertIn("public-room", aggregate_board["resolved_room_ids"])

        self.assertEqual(restricted_board["requested_room_id"], "restricted-room")
        self.assertEqual(restricted_board["resolved_room_ids"], ["restricted-room"])
        self.assertEqual(restricted_board["square_count"], 64)
        self.assertTrue(any(square["event_count"] > 0 for square in restricted_board["squares"]))

        self.assertEqual(
            square_detail["square"]["square_id"],
            f"{square_detail['square']['row_id']}:{square_detail['square']['column_id']}",
        )
        self.assertGreater(square_detail["source_count"], 0)
        self.assertGreater(len(square_detail["sources"]), 0)
        self.assertTrue(
            all(source["room_id"] == "restricted-room" for source in square_detail["sources"])
        )
        self.assertGreater(linked_square_detail["linked_cluster_count"], 0)
        self.assertGreater(linked_square_detail["linked_node_count"], 0)
        self.assertTrue(
            any(
                cluster["cluster_id"] == cluster_detail["cluster"]["cluster_id"]
                for cluster in linked_square_detail["linked_clusters"]
            )
        )
        self.assertTrue(
            any(
                node["node_id"] == node_detail["node"]["node_id"]
                for node in linked_square_detail["linked_nodes"]
            )
        )

        self.assertTrue(world_memory["read_only"])
        self.assertEqual(world_memory["requested_room_id"], "restricted-room")
        self.assertEqual(world_memory["resolved_room_ids"], ["restricted-room"])
        self.assertGreater(world_memory["node_count"], 0)
        self.assertGreater(world_memory["cluster_count"], 0)
        self.assertGreater(world_memory["place_candidate_count"], 0)
        self.assertGreater(world_memory["depth_candidate_count"], 0)
        self.assertTrue(
            any(node["relative_path"].endswith("scene.jpg") for node in world_memory["nodes"])
        )
        self.assertIn("image_scene", world_memory["anchor_types"])
        self.assertEqual(cluster_detail["requested_room_id"], "restricted-room")
        self.assertEqual(cluster_detail["cluster"]["room_id"], "restricted-room")
        self.assertGreater(cluster_detail["cluster"]["depth_candidate_count"], 0)
        self.assertGreater(len(cluster_detail["linked_squares"]), 0)
        self.assertTrue(
            any(
                square["square_id"] == node_detail["linked_square"]["square_id"]
                for square in cluster_detail["linked_squares"]
            )
        )
        self.assertTrue(cluster_detail["nodes"])
        self.assertEqual(node_detail["requested_room_id"], "restricted-room")
        self.assertEqual(node_detail["node"]["room_id"], "restricted-room")
        self.assertTrue(node_detail["place_shell"]["eligible"])
        self.assertTrue(node_detail["place_shell"]["depth_candidate"])
        self.assertEqual(node_detail["place_shell"]["stage"], "depth_anything_v2_candidate")
        self.assertEqual(node_detail["linked_square"]["square_id"], node_detail["node"]["primary_square_id"])

        self.assertEqual(aggregate_board, observed["aggregate_repeat"])
        self.assertEqual(world_memory, world_memory_repeat)

    async def _collect_board_payloads(self, app) -> dict[str, object]:
        async with app.router.lifespan_context(app):
            repository = app.state.repository
            self._ingest_dataset(
                repository=repository,
                label="Restricted Fixture",
                classification_level="personal",
                folder_name="restricted_fixture",
                files={"notes\\alpha.txt": "alpha", "images\\scene.jpg": "beta"},
            )
            self._ingest_dataset(
                repository=repository,
                label="Public Fixture",
                classification_level="public",
                folder_name="public_fixture",
                files={"readme.txt": "gamma"},
            )

            aggregate = simulation_hybrid_board(
                room_id=None,
                services=app.state.services,
            ).model_dump(mode="json")
            restricted = simulation_hybrid_board(
                room_id="restricted-room",
                services=app.state.services,
            ).model_dump(mode="json")
            active_square = next(
                square
                for square in restricted["squares"]
                if square["event_count"] > 0 or square["episode_count"] > 0 or square["audit_count"] > 0
            )
            square_detail = simulation_hybrid_board_square_detail(
                row_id=active_square["row_id"],
                column_id=active_square["column_id"],
                room_id="restricted-room",
                services=app.state.services,
            ).model_dump(mode="json")
            world_memory = simulation_world_memory(
                room_id="restricted-room",
                services=app.state.services,
            ).model_dump(mode="json")
            depth_node = next(node for node in world_memory["nodes"] if node["depth_candidate"])
            cluster_detail = simulation_world_memory_cluster_detail(
                cluster_id=depth_node["cluster_id"],
                room_id="restricted-room",
                services=app.state.services,
            ).model_dump(mode="json")
            node_detail = simulation_world_memory_node_detail(
                node_id=depth_node["node_id"],
                room_id="restricted-room",
                services=app.state.services,
            ).model_dump(mode="json")
            linked_square_detail = simulation_hybrid_board_square_detail(
                row_id=node_detail["linked_square"]["row_id"],
                column_id=node_detail["linked_square"]["column_id"],
                room_id="restricted-room",
                services=app.state.services,
            ).model_dump(mode="json")
            aggregate_repeat = simulation_hybrid_board(
                room_id=None,
                services=app.state.services,
            ).model_dump(mode="json")
            world_memory_repeat = simulation_world_memory(
                room_id="restricted-room",
                services=app.state.services,
            ).model_dump(mode="json")
            return {
                "aggregate": aggregate,
                "restricted": restricted,
                "square_detail": square_detail,
                "linked_square_detail": linked_square_detail,
                "world_memory": world_memory,
                "cluster_detail": cluster_detail,
                "node_detail": node_detail,
                "aggregate_repeat": aggregate_repeat,
                "world_memory_repeat": world_memory_repeat,
            }

    def _ingest_dataset(
        self,
        *,
        repository,
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
        return ingest_dataset(repository, request)

    def _settings_for(self, database_name: str) -> Settings:
        database_path = self.root / database_name
        return Settings(
            app_name="Klone Simulation Test",
            environment="test",
            owner_debug_mode=True,
            project_root=PROJECT_ROOT,
            data_dir=self.root / "data",
            sqlite_path=database_path,
            asset_preview_limit=12,
            audit_preview_limit=9,
        )


if __name__ == "__main__":
    unittest.main()
