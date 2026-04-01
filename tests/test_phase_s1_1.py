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
    asset_content,
    simulation_hybrid_board,
    simulation_hybrid_board_square_detail,
    simulation_world_memory,
    simulation_world_memory_cluster_detail,
    simulation_world_memory_depth_artifact,
    simulation_world_memory_depth_job_detail,
    simulation_world_memory_depth_jobs,
    simulation_world_memory_depth_run_job,
    simulation_world_memory_node_detail,
    simulation_world_memory_place_view,
)
from klone.config import Settings  # noqa: E402
from klone.ingest import ingest_dataset  # noqa: E402
from klone.main import create_app  # noqa: E402
from klone.schemas import DatasetIngestRequest, WorldMemoryDepthJobRequest  # noqa: E402


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
            any(node["relative_path"].endswith("scene.png") for node in world_memory["nodes"])
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

    def test_world_memory_depth_jobs_and_place_view_are_local_and_bounded(self) -> None:
        app = create_app(self._settings_for("simulation_depth.sqlite"))
        observed = asyncio.run(self._collect_depth_payloads(app))

        self.assertEqual(observed["jobs_before"]["job_count"], 0)
        self.assertFalse(observed["place_before"]["available"])

        job = observed["job"]
        self.assertEqual(job["status"], "completed")
        self.assertEqual(job["renderer"], "local_luma_shell")
        self.assertEqual(job["result_count"], 1)
        self.assertEqual(len(job["results"]), 1)

        job_list = observed["jobs_after"]
        self.assertEqual(job_list["job_count"], 1)
        self.assertEqual(job_list["jobs"][0]["job_id"], job["job_id"])

        job_detail = observed["job_detail"]
        self.assertEqual(job_detail["job_id"], job["job_id"])
        self.assertEqual(job_detail["result_count"], 1)
        self.assertEqual(job_detail["results"][0]["node_id"], observed["node_id"])

        self.assertTrue(Path(observed["preview_response"].path).exists())
        self.assertTrue(Path(observed["raw_response"].path).exists())
        self.assertTrue(Path(observed["asset_response"].path).exists())

        self.assertTrue(observed["place_after"]["available"])
        self.assertEqual(observed["place_after"]["latest_job_id"], job["job_id"])
        self.assertIn("/api/assets/", observed["place_after"]["source_image_route"])
        self.assertIn("/api/simulation/world-memory/depth/jobs/", observed["place_after"]["depth_preview_route"])

    async def _collect_board_payloads(self, app) -> dict[str, object]:
        async with app.router.lifespan_context(app):
            repository = app.state.repository
            self._ingest_dataset(
                repository=repository,
                label="Restricted Fixture",
                classification_level="personal",
                folder_name="restricted_fixture",
                files={
                    "notes\\alpha.txt": "alpha",
                    "images\\scene.png": (28, 18, (140, 70, 30)),
                },
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

    async def _collect_depth_payloads(self, app) -> dict[str, object]:
        async with app.router.lifespan_context(app):
            repository = app.state.repository
            self._ingest_dataset(
                repository=repository,
                label="Restricted Depth Fixture",
                classification_level="personal",
                folder_name="restricted_depth_fixture",
                files={
                    "notes\\alpha.txt": "alpha",
                    "images\\scene.png": (32, 20, (90, 120, 180)),
                },
            )

            world_memory = simulation_world_memory(
                room_id="restricted-room",
                services=app.state.services,
            ).model_dump(mode="json")
            depth_node = next(node for node in world_memory["nodes"] if node["depth_candidate"])

            jobs_before = simulation_world_memory_depth_jobs(
                room_id="restricted-room",
                services=app.state.services,
            ).model_dump(mode="json")
            place_before = simulation_world_memory_place_view(
                node_id=depth_node["node_id"],
                room_id="restricted-room",
                services=app.state.services,
            ).model_dump(mode="json")

            job = simulation_world_memory_depth_run_job(
                request=WorldMemoryDepthJobRequest(
                    node_ids=[depth_node["node_id"]],
                    renderer="local_luma_shell",
                ),
                room_id="restricted-room",
                services=app.state.services,
            ).model_dump(mode="json")
            jobs_after = simulation_world_memory_depth_jobs(
                room_id="restricted-room",
                services=app.state.services,
            ).model_dump(mode="json")
            job_detail = simulation_world_memory_depth_job_detail(
                job_id=job["job_id"],
                room_id="restricted-room",
                services=app.state.services,
            ).model_dump(mode="json")
            preview_response = simulation_world_memory_depth_artifact(
                job_id=job["job_id"],
                node_id=depth_node["node_id"],
                artifact_kind="preview",
                room_id="restricted-room",
                services=app.state.services,
            )
            raw_response = simulation_world_memory_depth_artifact(
                job_id=job["job_id"],
                node_id=depth_node["node_id"],
                artifact_kind="raw",
                room_id="restricted-room",
                services=app.state.services,
            )
            asset_response = asset_content(depth_node["asset_id"], repository=repository)
            place_after = simulation_world_memory_place_view(
                node_id=depth_node["node_id"],
                room_id="restricted-room",
                services=app.state.services,
            ).model_dump(mode="json")

            return {
                "node_id": depth_node["node_id"],
                "jobs_before": jobs_before,
                "place_before": place_before,
                "job": job,
                "jobs_after": jobs_after,
                "job_detail": job_detail,
                "preview_response": preview_response,
                "raw_response": raw_response,
                "asset_response": asset_response,
                "place_after": place_after,
            }

    def _ingest_dataset(
        self,
        *,
        repository,
        label: str,
        classification_level: str,
        folder_name: str,
        files: dict[str, object],
    ) -> dict:
        folder = self.root / folder_name
        folder.mkdir(parents=True, exist_ok=True)
        for relative_name, content in files.items():
            target = folder / relative_name
            target.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, tuple) and len(content) == 3 and isinstance(content[0], int):
                from PIL import Image

                width, height, color = content
                Image.new("RGB", (width, height), color).save(target)
            elif isinstance(content, bytes):
                target.write_bytes(content)
            else:
                target.write_text(str(content), encoding="utf-8")

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
