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

from klone.api import simulation_hybrid_board  # noqa: E402
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

        self.assertEqual(aggregate_board, observed["aggregate_repeat"])

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
            aggregate_repeat = simulation_hybrid_board(
                room_id=None,
                services=app.state.services,
            ).model_dump(mode="json")
            return {
                "aggregate": aggregate,
                "restricted": restricted,
                "aggregate_repeat": aggregate_repeat,
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
