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
from klone.v1_api import router as v1_router  # noqa: E402


class PhaseA16Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.database_path = self.root / "phase_a1_6.sqlite"
        self.repository = KloneRepository(self.database_path)
        self.repository.initialize()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_v1_query_returns_room_scoped_memory_event_and_episode_lists(self) -> None:
        ingest_result = self._ingest_dataset(
            label="Query Fixture",
            classification_level="personal",
            folder_name="query_fixture",
            files={"note.txt": "alpha"},
        )
        room_id = ingest_result["dataset"]["room_id"]
        self._seed_room(room_id)
        app = create_app(self._settings_for("phase_a1_6.sqlite"))

        event_response = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path=f"/v1/rooms/{room_id}/query",
                body={"query_kind": "memory_events", "limit": 10, "offset": 0},
            )
        )
        episode_response = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path=f"/v1/rooms/{room_id}/query",
                body={"query_kind": "memory_episodes", "limit": 10, "offset": 0},
            )
        )

        self.assertEqual(event_response["status_code"], 200)
        self.assertEqual(event_response["json"]["room_id"], room_id)
        self.assertEqual(event_response["json"]["query_kind"], "memory_events")
        self.assertGreaterEqual(event_response["json"]["result_count"], 1)
        self.assertEqual(len(event_response["json"]["results"]), event_response["json"]["result_count"])
        self.assertIn("id", event_response["json"]["results"][0])
        self.assertIn("provenance_summary", event_response["json"]["results"][0])

        self.assertEqual(episode_response["status_code"], 200)
        self.assertEqual(episode_response["json"]["query_kind"], "memory_episodes")
        self.assertGreaterEqual(episode_response["json"]["result_count"], 1)
        self.assertEqual(len(episode_response["json"]["results"]), episode_response["json"]["result_count"])
        self.assertIn("id", episode_response["json"]["results"][0])
        self.assertIn("provenance_summary", episode_response["json"]["results"][0])

    def test_v1_query_preserves_deterministic_memory_list_semantics(self) -> None:
        ingest_result = self._ingest_dataset(
            label="Deterministic Query Fixture",
            classification_level="personal",
            folder_name="deterministic_query_fixture",
            files={"note.txt": "alpha"},
        )
        room_id = ingest_result["dataset"]["room_id"]
        self._seed_room(room_id)
        memory_service = MemoryService(self.repository)
        app = create_app(self._settings_for("phase_a1_6.sqlite"))

        expected_events = memory_service.query_events(
            room_id=room_id,
            limit=5,
            offset=0,
            status="active",
            include_corrected=False,
        )
        expected_episodes = memory_service.query_episodes(
            room_id=room_id,
            limit=5,
            offset=0,
            status="active",
            episode_type="system_ingest_run",
            include_corrected=False,
        )

        event_response = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path=f"/v1/rooms/{room_id}/query",
                body={
                    "query_kind": "memory_events",
                    "limit": 5,
                    "offset": 0,
                    "status": "active",
                    "include_corrected": False,
                },
            )
        )
        episode_response = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path=f"/v1/rooms/{room_id}/query",
                body={
                    "query_kind": "memory_episodes",
                    "limit": 5,
                    "offset": 0,
                    "status": "active",
                    "episode_type": "system_ingest_run",
                    "include_corrected": False,
                },
            )
        )

        self.assertEqual(event_response["status_code"], 200)
        self.assertEqual(
            [item["id"] for item in event_response["json"]["results"]],
            [item["id"] for item in expected_events],
        )
        self.assertEqual(
            event_response["json"]["filters"],
            {"status": "active", "include_corrected": False},
        )

        self.assertEqual(episode_response["status_code"], 200)
        self.assertEqual(
            [item["id"] for item in episode_response["json"]["results"]],
            [item["id"] for item in expected_episodes],
        )
        self.assertEqual(
            episode_response["json"]["filters"],
            {
                "status": "active",
                "episode_type": "system_ingest_run",
                "include_corrected": False,
            },
        )

    def test_v1_query_rejects_invalid_query_kind_and_audits_failures(self) -> None:
        ingest_result = self._ingest_dataset(
            label="Invalid Query Fixture",
            classification_level="personal",
            folder_name="invalid_query_fixture",
            files={"note.txt": "alpha"},
        )
        room_id = ingest_result["dataset"]["room_id"]
        self._seed_room(room_id)
        app = create_app(self._settings_for("phase_a1_6.sqlite"))

        valid = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path=f"/v1/rooms/{room_id}/query",
                body={"query_kind": "memory_events", "limit": 5, "offset": 0},
                headers={"x-request-id": "req:a16-1", "x-trace-id": "trace:a16-1"},
            )
        )
        invalid = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path=f"/v1/rooms/{room_id}/query",
                body={"query_kind": "memory_entities", "limit": 5, "offset": 0},
                headers={"x-request-id": "req:a16-2", "x-trace-id": "trace:a16-2"},
            )
        )

        self.assertEqual(valid["status_code"], 200)
        self.assertEqual(invalid["status_code"], 422)

        query_rows = [
            row
            for row in self.repository.list_control_plane_audit_chain(limit=10)
            if row["event_type"] == "v1_query_read"
        ]
        self.assertGreaterEqual(len(query_rows), 1)
        latest = query_rows[0]
        self.assertEqual(latest["request_id"], "req:a16-1")
        self.assertEqual(latest["status_code"], 200)
        self.assertEqual(latest["route_path"], f"/v1/rooms/{room_id}/query")

    def test_v1_capabilities_exposes_public_query_route_and_contract(self) -> None:
        app = create_app(self._settings_for("phase_a1_6.sqlite"))
        observed = asyncio.run(self._perform_request(app, method="GET", path="/v1/capabilities"))

        self.assertEqual(observed["status_code"], 200)
        payload = observed["json"]
        capabilities = {item["id"]: item for item in payload["capabilities"]}
        self.assertEqual(capabilities["v1.query.read"]["path"], "/v1/rooms/{room_id}/query")
        self.assertEqual(capabilities["v1.query.read"]["methods"], ["POST"])
        self.assertTrue(capabilities["v1.query.read"]["read_only"])
        self.assertTrue(capabilities["v1.query.read"]["room_scoped"])

        contracts = {item["id"]: item for item in payload["contracts"]}
        self.assertEqual(contracts["query-shell"]["route_readiness"], "public_read_only_query_available")
        self.assertIn("/v1/rooms/{room_id}/query", contracts["query-shell"]["backing_routes"])

    def test_v1_surface_contains_capabilities_object_get_and_query(self) -> None:
        v1_routes = {
            route.path: sorted(route.methods)
            for route in v1_router.routes
            if route.path.startswith("/v1")
        }
        self.assertEqual(v1_routes["/v1/capabilities"], ["GET"])
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
                "client": ("127.0.0.1", 50008),
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
            app_name="Klone Phase A1.6 Test",
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
