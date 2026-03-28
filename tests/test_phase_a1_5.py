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
from klone.schemas import DatasetIngestRequest  # noqa: E402
from klone.services import ServiceContainer  # noqa: E402
from klone.v1_api import router as v1_router  # noqa: E402


class PhaseA15Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.database_path = self.root / "phase_a1_5.sqlite"
        self.repository = KloneRepository(self.database_path)
        self.repository.initialize()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_v1_object_get_returns_room_scoped_dataset_and_memory_envelopes(self) -> None:
        ingest_result = self._ingest_dataset(
            label="Object Get Fixture",
            classification_level="personal",
            folder_name="object_get_fixture",
            files={"note.txt": "alpha"},
        )
        room_id = ingest_result["dataset"]["room_id"]
        self._seed_room(room_id)
        services = ServiceContainer.build(self.repository)
        event_envelope = services.object_envelope.list_memory_event_envelopes(room_id=room_id, limit=10)[0]
        episode_envelope = services.object_envelope.list_memory_episode_envelopes(room_id=room_id, limit=10)[0]

        app = create_app(self._settings_for("phase_a1_5.sqlite"))

        dataset_response = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path=f"/v1/rooms/{room_id}/objects/get",
                body={"object_id": f"dataset:{ingest_result['dataset']['id']}"},
                headers={"x-request-id": "req:a15-dataset", "x-trace-id": "trace:a15-dataset"},
            )
        )
        event_response = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path=f"/v1/rooms/{room_id}/objects/get",
                body={"object_id": event_envelope.object_id},
                headers={"x-request-id": "req:a15-event", "x-trace-id": "trace:a15-event"},
            )
        )
        episode_response = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path=f"/v1/rooms/{room_id}/objects/get",
                body={"object_id": episode_envelope.object_id},
                headers={"x-request-id": "req:a15-episode", "x-trace-id": "trace:a15-episode"},
            )
        )

        self.assertEqual(dataset_response["status_code"], 200)
        self.assertEqual(dataset_response["json"]["room_id"], room_id)
        self.assertEqual(dataset_response["json"]["object"]["object_kind"], "dataset")
        self.assertEqual(
            dataset_response["json"]["object"]["object_id"],
            f"dataset:{ingest_result['dataset']['id']}",
        )
        self.assertEqual(dataset_response["json"]["object"]["backing_routes"], ["/api/datasets"])
        self.assertEqual(dataset_response["json"]["object"]["record"]["label"], "Object Get Fixture")

        self.assertEqual(event_response["status_code"], 200)
        self.assertEqual(event_response["json"]["object"]["object_kind"], "memory_event")
        self.assertEqual(event_response["json"]["object"]["object_id"], event_envelope.object_id)
        self.assertEqual(
            event_response["json"]["object"]["backing_routes"],
            ["/api/memory/events", "/api/memory/events/{event_id}"],
        )
        self.assertIn("provenance", event_response["json"]["object"]["record"])
        self.assertIn("status", event_response["json"]["object"]["record"])

        self.assertEqual(episode_response["status_code"], 200)
        self.assertEqual(episode_response["json"]["object"]["object_kind"], "memory_episode")
        self.assertEqual(episode_response["json"]["object"]["object_id"], episode_envelope.object_id)
        self.assertEqual(
            episode_response["json"]["object"]["backing_routes"],
            ["/api/memory/episodes", "/api/memory/episodes/{episode_id}"],
        )
        self.assertIn("linked_events", episode_response["json"]["object"]["record"])
        self.assertIn("status", episode_response["json"]["object"]["record"])

    def test_v1_object_get_blocks_wrong_room_and_unsupported_kind(self) -> None:
        restricted = self._ingest_dataset(
            label="Restricted Get Fixture",
            classification_level="personal",
            folder_name="restricted_get_fixture",
            files={"restricted.txt": "alpha"},
        )
        public = self._ingest_dataset(
            label="Public Get Fixture",
            classification_level="public",
            folder_name="public_get_fixture",
            files={"public.txt": "beta"},
        )
        self._seed_room(restricted["dataset"]["room_id"])
        self._seed_room(public["dataset"]["room_id"])

        app = create_app(self._settings_for("phase_a1_5.sqlite"))
        wrong_room = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path=f"/v1/rooms/{public['dataset']['room_id']}/objects/get",
                body={"object_id": f"dataset:{restricted['dataset']['id']}"},
                headers={"x-request-id": "req:a15-wrong-room"},
            )
        )
        unsupported = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path=f"/v1/rooms/{restricted['dataset']['room_id']}/objects/get",
                body={"object_id": "memory_entity:1"},
                headers={"x-request-id": "req:a15-unsupported"},
            )
        )

        self.assertEqual(wrong_room["status_code"], 404)
        self.assertIn("was not found", wrong_room["json"]["detail"])
        self.assertEqual(unsupported["status_code"], 400)
        self.assertIn("Unsupported object kind", unsupported["json"]["detail"])

    def test_v1_object_get_writes_append_only_audit_chain(self) -> None:
        ingest_result = self._ingest_dataset(
            label="Audit Get Fixture",
            classification_level="personal",
            folder_name="audit_get_fixture",
            files={"note.txt": "alpha"},
        )
        room_id = ingest_result["dataset"]["room_id"]
        self._seed_room(room_id)
        app = create_app(self._settings_for("phase_a1_5.sqlite"))

        first = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path=f"/v1/rooms/{room_id}/objects/get",
                body={"object_id": f"dataset:{ingest_result['dataset']['id']}"},
                headers={
                    "x-request-id": "req:a15-1",
                    "x-trace-id": "trace:a15-1",
                    "x-klone-principal": "owner:a15",
                    "x-klone-role": "owner",
                },
            )
        )
        second = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path=f"/v1/rooms/{room_id}/objects/get",
                body={"object_id": "memory_entity:1"},
                headers={
                    "x-request-id": "req:a15-2",
                    "x-trace-id": "trace:a15-2",
                    "x-klone-principal": "owner:a15",
                    "x-klone-role": "owner",
                },
            )
        )

        self.assertEqual(first["status_code"], 200)
        self.assertEqual(second["status_code"], 400)

        chain_rows = self.repository.list_control_plane_audit_chain(limit=10)
        object_rows = [row for row in chain_rows if row["event_type"] == "v1_object_get"]
        self.assertGreaterEqual(len(object_rows), 2)

        latest = object_rows[0]
        older = object_rows[1]
        self.assertEqual(latest["request_id"], "req:a15-2")
        self.assertEqual(latest["trace_id"], "trace:a15-2")
        self.assertEqual(latest["status_code"], 400)
        self.assertEqual(latest["route_path"], f"/v1/rooms/{room_id}/objects/get")
        self.assertEqual(older["request_id"], "req:a15-1")
        self.assertEqual(older["status_code"], 200)
        self.assertEqual(latest["prev_event_hash"], older["event_hash"])

    def test_v1_capabilities_exposes_public_object_get_route(self) -> None:
        app = create_app(self._settings_for("phase_a1_5.sqlite"))
        observed = asyncio.run(self._perform_request(app, method="GET", path="/v1/capabilities"))

        self.assertEqual(observed["status_code"], 200)
        payload = observed["json"]
        capabilities = {item["id"]: item for item in payload["capabilities"]}
        self.assertEqual(capabilities["v1.objects.get"]["path"], "/v1/rooms/{room_id}/objects/get")
        self.assertEqual(capabilities["v1.objects.get"]["methods"], ["POST"])
        self.assertTrue(capabilities["v1.objects.get"]["read_only"])
        self.assertTrue(capabilities["v1.objects.get"]["room_scoped"])

        contracts = {item["id"]: item for item in payload["contracts"]}
        self.assertEqual(contracts["object-shell"]["route_readiness"], "public_read_only_get_available")
        self.assertIn("/v1/rooms/{room_id}/objects/get", contracts["object-shell"]["backing_routes"])

    def test_v1_surface_contains_blob_get_object_get_and_query(self) -> None:
        v1_routes = {
            route.path: sorted(route.methods)
            for route in v1_router.routes
            if route.path.startswith("/v1")
        }
        self.assertEqual(v1_routes["/v1/capabilities"], ["GET"])
        self.assertEqual(v1_routes["/v1/rooms/{room_id}/blobs/{blob_id}/meta"], ["GET"])
        self.assertEqual(v1_routes["/v1/rooms/{room_id}/objects/get"], ["POST"])
        self.assertEqual(v1_routes["/v1/rooms/{room_id}/query"], ["POST"])

    async def _perform_request(
        self,
        app,
        *,
        method: str,
        path: str,
        body: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, object]:
        async with app.router.lifespan_context(app):
            events: list[dict] = []
            body_bytes = json.dumps(body).encode("utf-8") if body is not None else b""
            request_headers = dict(headers or {})
            if body is not None:
                request_headers.setdefault("content-type", "application/json")
            header_items = [
                (key.lower().encode("utf-8"), value.encode("utf-8"))
                for key, value in request_headers.items()
            ]
            scope = {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": method,
                "scheme": "http",
                "path": path,
                "raw_path": path.encode("utf-8"),
                "query_string": b"",
                "headers": header_items,
                "client": ("127.0.0.1", 50006),
                "server": ("testserver", 80),
                "app": app,
            }

            sent = False

            async def receive():
                nonlocal sent
                if sent:
                    return {"type": "http.disconnect"}
                sent = True
                return {"type": "http.request", "body": body_bytes, "more_body": False}

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

    def _seed_room(self, room_id: str) -> None:
        MemoryService(self.repository).seed_from_audit_events(
            room_id=room_id,
            audit_event_ids=[row["id"] for row in self.repository.list_audit_events(room_id=room_id, limit=20)],
        )

    def _settings_for(self, database_name: str) -> Settings:
        database_path = self.root / database_name
        return Settings(
            app_name="Klone Phase A1.5 Test",
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
