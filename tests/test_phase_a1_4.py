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

    def test_object_envelope_service_projects_existing_read_models_deterministically(self) -> None:
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

        dataset_record = dataset_envelopes[0]
        asset_record = asset_envelopes[0]
        event_record = event_envelopes[0]
        episode_record = episode_envelopes[0]

        for record in [dataset_record, asset_record, event_record, episode_record]:
            self.assertIsInstance(record, ObjectEnvelopeRecord)
            self.assertEqual(record.version, 1)
            self.assertEqual(record.room_id, room_id)
            self.assertTrue(record.read_only)
            self.assertTrue(record.backing_routes)
            self.assertTrue(record.record)

        self.assertEqual(dataset_record.object_kind, "dataset")
        self.assertEqual(dataset_record.object_id, f"dataset:{ingest_result['dataset']['id']}")
        self.assertEqual(dataset_record.backing_routes, ["/api/datasets"])
        self.assertEqual(dataset_record.record["id"], ingest_result["dataset"]["id"])
        self.assertEqual(dataset_record.record["label"], "Object Shell Fixture")

        self.assertEqual(asset_record.object_kind, "asset")
        self.assertTrue(asset_record.object_id.startswith("asset:"))
        self.assertEqual(asset_record.backing_routes, ["/api/assets", "/api/assets/{asset_id}"])
        self.assertEqual(asset_record.record["relative_path"], "note.txt")
        self.assertEqual(asset_record.record["metadata"]["source"], "recursive_file_scan")

        self.assertEqual(event_record.object_kind, "memory_event")
        self.assertTrue(event_record.object_id.startswith("memory_event:"))
        self.assertEqual(
            event_record.backing_routes,
            ["/api/memory/events", "/api/memory/events/{event_id}"],
        )
        self.assertIn("provenance", event_record.record)
        self.assertIn("provenance_summary", event_record.record)
        self.assertIn("episode_memberships", event_record.record)
        self.assertFalse(event_record.record["corrected"])

        self.assertEqual(episode_record.object_kind, "memory_episode")
        self.assertTrue(episode_record.object_id.startswith("memory_episode:"))
        self.assertEqual(
            episode_record.backing_routes,
            ["/api/memory/episodes", "/api/memory/episodes/{episode_id}"],
        )
        self.assertIn("linked_events", episode_record.record)
        self.assertIn("provenance_summary", episode_record.record)
        self.assertEqual(episode_record.record["status"], "active")

        self.assertEqual(
            [item.model_dump(mode="json") for item in services.object_envelope.list_dataset_envelopes(room_id=room_id)],
            [item.model_dump(mode="json") for item in services.object_envelope.list_dataset_envelopes(room_id=room_id)],
        )
        self.assertEqual(
            [
                item.model_dump(mode="json")
                for item in services.object_envelope.list_asset_envelopes(room_id=room_id, limit=10)
            ],
            [
                item.model_dump(mode="json")
                for item in services.object_envelope.list_asset_envelopes(room_id=room_id, limit=10)
            ],
        )
        self.assertEqual(
            [
                item.model_dump(mode="json")
                for item in services.object_envelope.list_memory_event_envelopes(room_id=room_id, limit=10)
            ],
            [
                item.model_dump(mode="json")
                for item in services.object_envelope.list_memory_event_envelopes(room_id=room_id, limit=10)
            ],
        )
        self.assertEqual(
            [
                item.model_dump(mode="json")
                for item in services.object_envelope.list_memory_episode_envelopes(room_id=room_id, limit=10)
            ],
            [
                item.model_dump(mode="json")
                for item in services.object_envelope.list_memory_episode_envelopes(room_id=room_id, limit=10)
            ],
        )

    def test_object_envelope_reads_remain_room_scoped_and_side_effect_free(self) -> None:
        restricted_result = self._ingest_dataset(
            label="Restricted Object Shell",
            classification_level="personal",
            folder_name="restricted_object_shell",
            files={"restricted.txt": "alpha"},
        )
        public_result = self._ingest_dataset(
            label="Public Object Shell",
            classification_level="public",
            folder_name="public_object_shell",
            files={"public.txt": "beta"},
        )
        restricted_room = restricted_result["dataset"]["room_id"]
        public_room = public_result["dataset"]["room_id"]
        memory_service = MemoryService(self.repository)
        for room_id in (restricted_room, public_room):
            memory_service.seed_from_audit_events(
                room_id=room_id,
                audit_event_ids=[row["id"] for row in self.repository.list_audit_events(room_id=room_id, limit=20)],
            )

        services = ServiceContainer.build(self.repository)
        restricted_before = self._room_snapshot(restricted_room)
        public_before = self._room_snapshot(public_room)
        control_before = self.repository.list_control_plane_audit_chain(limit=20)
        internal_before = self.repository.list_internal_runs(limit=20)

        restricted_dataset_envelopes = services.object_envelope.list_dataset_envelopes(room_id=restricted_room)
        restricted_asset_envelopes = services.object_envelope.list_asset_envelopes(room_id=restricted_room, limit=10)
        restricted_event_envelopes = services.object_envelope.list_memory_event_envelopes(
            room_id=restricted_room,
            limit=10,
        )
        restricted_episode_envelopes = services.object_envelope.list_memory_episode_envelopes(
            room_id=restricted_room,
            limit=10,
        )
        public_dataset_envelopes = services.object_envelope.list_dataset_envelopes(room_id=public_room)
        public_asset_envelopes = services.object_envelope.list_asset_envelopes(room_id=public_room, limit=10)

        self.assertTrue(all(item.room_id == restricted_room for item in restricted_dataset_envelopes))
        self.assertTrue(all(item.room_id == restricted_room for item in restricted_asset_envelopes))
        self.assertTrue(all(item.room_id == restricted_room for item in restricted_event_envelopes))
        self.assertTrue(all(item.room_id == restricted_room for item in restricted_episode_envelopes))
        self.assertTrue(all(item.room_id == public_room for item in public_dataset_envelopes))
        self.assertTrue(all(item.room_id == public_room for item in public_asset_envelopes))
        self.assertTrue(
            {item.object_id for item in restricted_dataset_envelopes}.isdisjoint(
                {item.object_id for item in public_dataset_envelopes}
            )
        )
        self.assertTrue(
            {item.object_id for item in restricted_asset_envelopes}.isdisjoint(
                {item.object_id for item in public_asset_envelopes}
            )
        )

        self.assertEqual(self._room_snapshot(restricted_room), restricted_before)
        self.assertEqual(self._room_snapshot(public_room), public_before)
        self.assertEqual(self.repository.list_control_plane_audit_chain(limit=20), control_before)
        self.assertEqual(self.repository.list_internal_runs(limit=20), internal_before)

    def test_v1_capabilities_exposes_object_shell_readiness_without_new_v1_route(self) -> None:
        app = create_app(self._settings_for("phase_a1_4_app.sqlite"))
        observed = asyncio.run(self._perform_request(app, path="/v1/capabilities"))

        self.assertEqual(observed["status_code"], 200)
        payload = observed["json"]
        contracts = {item["id"]: item for item in payload["contracts"]}
        object_shell = contracts["object-shell"]

        self.assertEqual(object_shell["route_readiness"], "public_read_only_get_available")
        self.assertEqual(
            object_shell["backing_routes"],
            [
                "/v1/rooms/{room_id}/objects/get",
                "/api/datasets",
                "/api/assets",
                "/api/memory/events",
                "/api/memory/episodes",
            ],
        )
        self.assertIn(
            "POST /v1/rooms/{room_id}/objects/get is the first public read-only object route.",
            object_shell["notes"],
        )

        capabilities = {item["id"]: item for item in payload["capabilities"]}
        self.assertEqual(capabilities["v1.objects.get"]["path"], "/v1/rooms/{room_id}/objects/get")
        self.assertEqual(capabilities["v1.objects.get"]["methods"], ["POST"])
        self.assertEqual(capabilities["object.envelope.dataset"]["path"], "/api/datasets")
        self.assertEqual(capabilities["object.envelope.asset"]["path"], "/api/assets")
        self.assertEqual(capabilities["object.envelope.memory_event"]["path"], "/api/memory/events")
        self.assertEqual(capabilities["object.envelope.memory_episode"]["path"], "/api/memory/episodes")

    def test_v1_surface_contains_blob_object_and_query_routes_after_a1_4(self) -> None:
        v1_routes = {
            route.path: sorted(route.methods)
            for route in v1_router.routes
            if route.path.startswith("/v1")
        }
        self.assertEqual(v1_routes["/v1/capabilities"], ["GET"])
        self.assertEqual(v1_routes["/v1/rooms/{room_id}/blobs/get"], ["POST"])
        self.assertEqual(v1_routes["/v1/rooms/{room_id}/objects/get"], ["POST"])
        self.assertEqual(v1_routes["/v1/rooms/{room_id}/query"], ["POST"])

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

    def _room_snapshot(self, room_id: str) -> dict[str, object]:
        return {
            "datasets": [row["id"] for row in self.repository.list_datasets(room_id=room_id)],
            "assets": [row["id"] for row in self.repository.list_assets(room_id=room_id, limit=50)],
            "memory_events": [
                row["id"]
                for row in self.repository.list_memory_events(
                    room_id=room_id,
                    limit=100,
                    offset=0,
                    include_corrected=True,
                )
            ],
            "memory_episodes": [
                row["id"]
                for row in self.repository.list_memory_episodes(
                    room_id=room_id,
                    limit=100,
                    offset=0,
                    include_corrected=True,
                )
            ],
            "audit_events": [row["id"] for row in self.repository.list_audit_events(room_id=room_id, limit=50)],
        }


if __name__ == "__main__":
    unittest.main()
