from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from klone.config import Settings  # noqa: E402
from klone.ingest import ingest_dataset  # noqa: E402
from klone.main import create_app  # noqa: E402
from klone.memory import MemoryService  # noqa: E402
from klone.repository import KloneRepository  # noqa: E402
from klone.schemas import DatasetIngestRequest, ObjectEnvelopeRecord  # noqa: E402
from klone.services import ServiceContainer  # noqa: E402
from klone.v1_api import router as v1_router  # noqa: E402


class PhaseA14Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.repository = KloneRepository(self.root / "phase_a1_4.sqlite")
        self.repository.initialize()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_object_envelope_service_projects_existing_read_models(self) -> None:
        ingest_result = self._ingest_dataset(
            label="Object Shell Fixture",
            classification_level="personal",
            folder_name="object_shell_fixture",
            files={"note.txt": "alpha"},
        )
        room_id = ingest_result["dataset"]["room_id"]
        memory_service = MemoryService(self.repository)
        audit_ids = [
            row["id"]
            for row in self.repository.list_audit_events(room_id=room_id, limit=20)
        ]
        memory_service.seed_from_audit_events(
            room_id=room_id,
            audit_event_ids=audit_ids,
        )
        services = ServiceContainer.build(self.repository)

        dataset_envelopes = services.object_envelope.list_dataset_envelopes(room_id=room_id)
        asset_envelopes = services.object_envelope.list_asset_envelopes(room_id=room_id, limit=10)
        event_envelopes = services.object_envelope.list_memory_event_envelopes(room_id=room_id, limit=10)
        episode_envelopes = services.object_envelope.list_memory_episode_envelopes(room_id=room_id, limit=10)

        self.assertGreaterEqual(len(dataset_envelopes), 1)
        self.assertGreaterEqual(len(asset_envelopes), 1)
        self.assertGreaterEqual(len(event_envelopes), 1)
        self.assertGreaterEqual(len(episode_envelopes), 1)

        for record in [
            dataset_envelopes[0],
            asset_envelopes[0],
            event_envelopes[0],
            episode_envelopes[0],
        ]:
            self.assertIsInstance(record, ObjectEnvelopeRecord)
            self.assertEqual(record.version, 1)
            self.assertEqual(record.room_id, room_id)

        self.assertEqual(dataset_envelopes[0].object_kind, "dataset")
        self.assertTrue(dataset_envelopes[0].object_id.startswith("dataset:"))
        self.assertTrue(dataset_envelopes[0].read_only)
        self.assertEqual(dataset_envelopes[0].backing_routes, ["/api/datasets"])
        self.assertEqual(dataset_envelopes[0].record["label"], "Object Shell Fixture")
        self.assertEqual(asset_envelopes[0].object_kind, "asset")
        self.assertTrue(asset_envelopes[0].object_id.startswith("asset:"))
        self.assertEqual(asset_envelopes[0].backing_routes, ["/api/assets", "/api/assets/{asset_id}"])
        self.assertEqual(asset_envelopes[0].record["relative_path"], "note.txt")
        self.assertEqual(event_envelopes[0].object_kind, "memory_event")
        self.assertTrue(event_envelopes[0].object_id.startswith("memory_event:"))
        self.assertEqual(
            event_envelopes[0].backing_routes,
            ["/api/memory/events", "/api/memory/events/{event_id}"],
        )
        self.assertIn("title", event_envelopes[0].record)
        self.assertEqual(episode_envelopes[0].object_kind, "memory_episode")
        self.assertTrue(episode_envelopes[0].object_id.startswith("memory_episode:"))
        self.assertEqual(
            episode_envelopes[0].backing_routes,
            ["/api/memory/episodes", "/api/memory/episodes/{episode_id}"],
        )
        self.assertIn("title", episode_envelopes[0].record)

    def test_v1_capabilities_exposes_object_shell_readiness_without_new_v1_route(self) -> None:
        app = create_app(self._settings_for("phase_a1_4_app.sqlite"))
        observed = asyncio.run(self._perform_request(app, path="/v1/capabilities"))

        self.assertEqual(observed["status_code"], 200)
        payload = observed["json"]
        contracts = {item["id"]: item for item in payload["contracts"]}
        object_shell = contracts["object-shell"]

        self.assertEqual(object_shell["route_readiness"], "available_via_existing_read_routes")
        self.assertEqual(
            object_shell["backing_routes"],
            [
                "/api/datasets",
                "/api/assets",
                "/api/memory/events",
                "/api/memory/episodes",
            ],
        )
        self.assertIn("No public /v1 object route exists yet.", object_shell["notes"])

        capabilities = {item["id"]: item for item in payload["capabilities"]}
        self.assertEqual(capabilities["object.envelope.dataset"]["path"], "/api/datasets")
        self.assertEqual(capabilities["object.envelope.asset"]["path"], "/api/assets")
        self.assertEqual(capabilities["object.envelope.memory_event"]["path"], "/api/memory/events")
        self.assertEqual(capabilities["object.envelope.memory_episode"]["path"], "/api/memory/episodes")

    def test_v1_surface_remains_single_read_only_capabilities_route_after_a1_4(self) -> None:
        v1_routes = {
            route.path: sorted(route.methods)
            for route in v1_router.routes
            if route.path.startswith("/v1")
        }
        self.assertEqual(v1_routes, {"/v1/capabilities": ["GET"]})

    async def _perform_request(
        self,
        app,
        *,
        path: str,
        headers: dict[str, str] | None = None,
    ) -> dict[str, object]:
        async with app.router.lifespan_context(app):
            events: list[dict] = []
            header_items = [
                (key.lower().encode("utf-8"), value.encode("utf-8"))
                for key, value in (headers or {}).items()
            ]
            scope = {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": "GET",
                "scheme": "http",
                "path": path,
                "raw_path": path.encode("utf-8"),
                "query_string": b"",
                "headers": header_items,
                "client": ("127.0.0.1", 50005),
                "server": ("testserver", 80),
                "app": app,
            }

            async def receive():
                return {"type": "http.request", "body": b"", "more_body": False}

            async def send(message):
                events.append(message)

            await app(scope, receive, send)

            response_start = next(item for item in events if item["type"] == "http.response.start")
            response_body = b"".join(
                item.get("body", b"")
                for item in events
                if item["type"] == "http.response.body"
            )
            return {
                "status_code": response_start["status"],
                "json": json.loads(response_body.decode("utf-8")),
            }

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

    def _settings_for(self, database_name: str) -> Settings:
        database_path = self.root / database_name
        return Settings(
            app_name="Klone Phase A1.4 Test",
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
