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

    def test_v1_query_lists_room_scoped_dataset_pages_deterministically(self) -> None:
        first = self._ingest_dataset(
            label="Query Fixture One",
            classification_level="personal",
            folder_name="query_fixture_one",
            files={"one.txt": "alpha"},
        )
        second = self._ingest_dataset(
            label="Query Fixture Two",
            classification_level="personal",
            folder_name="query_fixture_two",
            files={"two.txt": "beta"},
        )
        room_id = first["dataset"]["room_id"]
        self._seed_room(room_id)
        app = create_app(self._settings_for("phase_a1_6.sqlite"))

        first_page = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path=f"/v1/rooms/{room_id}/query",
                body={
                    "query_id": "query:a16:datasets:first",
                    "query_kind": "object.envelopes.list",
                    "request_id": "req:a16-datasets:first",
                    "filters": {"object_kind": "dataset"},
                    "limit": 1,
                },
                headers={
                    "x-request-id": "req:a16-datasets:first",
                    "x-trace-id": "trace:a16-datasets:first",
                },
            )
        )
        repeated_first_page = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path=f"/v1/rooms/{room_id}/query",
                body={
                    "query_id": "query:a16:datasets:first",
                    "query_kind": "object.envelopes.list",
                    "request_id": "req:a16-datasets:first",
                    "filters": {"object_kind": "dataset"},
                    "limit": 1,
                },
                headers={
                    "x-request-id": "req:a16-datasets:first",
                    "x-trace-id": "trace:a16-datasets:first",
                },
            )
        )
        second_page = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path=f"/v1/rooms/{room_id}/query",
                body={
                    "query_id": "query:a16:datasets:second",
                    "query_kind": "object.envelopes.list",
                    "request_id": "req:a16-datasets:second",
                    "filters": {"object_kind": "dataset"},
                    "cursor": "1",
                    "limit": 1,
                },
                headers={
                    "x-request-id": "req:a16-datasets:second",
                    "x-trace-id": "trace:a16-datasets:second",
                },
            )
        )

        self.assertEqual(first_page["status_code"], 200)
        self.assertEqual(repeated_first_page["json"], first_page["json"])
        self.assertEqual(first_page["json"]["room_id"], room_id)
        self.assertEqual(first_page["json"]["query_kind"], "object.envelopes.list")
        self.assertEqual(first_page["json"]["applied_filters"], {"object_kind": "dataset"})
        self.assertEqual(len(first_page["json"]["items"]), 1)
        self.assertEqual(first_page["json"]["items"][0]["object_kind"], "dataset")
        self.assertEqual(first_page["json"]["items"][0]["backing_routes"], ["/api/datasets"])
        self.assertEqual(first_page["json"]["next_cursor"], "1")

        self.assertEqual(second_page["status_code"], 200)
        self.assertEqual(second_page["json"]["cursor"], "1")
        self.assertIsNone(second_page["json"]["next_cursor"])
        self.assertEqual(len(second_page["json"]["items"]), 1)
        self.assertNotEqual(
            first_page["json"]["items"][0]["object_id"],
            second_page["json"]["items"][0]["object_id"],
        )
        self.assertEqual(
            {
                first_page["json"]["items"][0]["record"]["label"],
                second_page["json"]["items"][0]["record"]["label"],
            },
            {"Query Fixture One", "Query Fixture Two"},
        )

    def test_v1_query_supports_asset_and_memory_kinds(self) -> None:
        ingest_result = self._ingest_dataset(
            label="Query Kind Fixture",
            classification_level="personal",
            folder_name="query_kind_fixture",
            files={"note.txt": "alpha"},
        )
        room_id = ingest_result["dataset"]["room_id"]
        self._seed_room(room_id)
        app = create_app(self._settings_for("phase_a1_6.sqlite"))

        observed_by_kind: dict[str, dict[str, object]] = {}
        for object_kind in ("asset", "memory_event", "memory_episode"):
            observed_by_kind[object_kind] = asyncio.run(
                self._perform_request(
                    app,
                    method="POST",
                    path=f"/v1/rooms/{room_id}/query",
                    body={
                        "query_id": f"query:a16:{object_kind}",
                        "query_kind": "object.envelopes.list",
                        "request_id": f"req:a16:{object_kind}",
                        "filters": {"object_kind": object_kind},
                        "limit": 5,
                    },
                    headers={
                        "x-request-id": f"req:a16:{object_kind}",
                        "x-trace-id": f"trace:a16:{object_kind}",
                    },
                )
            )

        self.assertEqual(observed_by_kind["asset"]["status_code"], 200)
        self.assertEqual(observed_by_kind["asset"]["json"]["items"][0]["object_kind"], "asset")
        self.assertEqual(
            observed_by_kind["asset"]["json"]["items"][0]["backing_routes"],
            ["/api/assets", "/api/assets/{asset_id}"],
        )

        self.assertEqual(observed_by_kind["memory_event"]["status_code"], 200)
        self.assertEqual(observed_by_kind["memory_event"]["json"]["items"][0]["object_kind"], "memory_event")
        self.assertIn("provenance", observed_by_kind["memory_event"]["json"]["items"][0]["record"])

        self.assertEqual(observed_by_kind["memory_episode"]["status_code"], 200)
        self.assertEqual(
            observed_by_kind["memory_episode"]["json"]["items"][0]["object_kind"],
            "memory_episode",
        )
        self.assertIn("linked_events", observed_by_kind["memory_episode"]["json"]["items"][0]["record"])

    def test_v1_query_blocks_invalid_shape_and_missing_room(self) -> None:
        ingest_result = self._ingest_dataset(
            label="Query Error Fixture",
            classification_level="personal",
            folder_name="query_error_fixture",
            files={"note.txt": "alpha"},
        )
        room_id = ingest_result["dataset"]["room_id"]
        self._seed_room(room_id)
        app = create_app(self._settings_for("phase_a1_6.sqlite"))

        missing_room = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path="/v1/rooms/missing-room/query",
                body={
                    "query_id": "query:a16:missing-room",
                    "query_kind": "object.envelopes.list",
                    "request_id": "req:a16:missing-room",
                    "filters": {"object_kind": "dataset"},
                },
                headers={"x-request-id": "req:a16:missing-room"},
            )
        )
        mismatched_request = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path=f"/v1/rooms/{room_id}/query",
                body={
                    "query_id": "query:a16:mismatch",
                    "query_kind": "object.envelopes.list",
                    "request_id": "req:a16:other",
                    "filters": {"object_kind": "dataset"},
                },
                headers={"x-request-id": "req:a16:mismatch"},
            )
        )
        unsupported_query_kind = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path=f"/v1/rooms/{room_id}/query",
                body={
                    "query_id": "query:a16:unsupported-kind",
                    "query_kind": "object.search",
                    "request_id": "req:a16:unsupported-kind",
                    "filters": {"object_kind": "dataset"},
                },
                headers={"x-request-id": "req:a16:unsupported-kind"},
            )
        )
        unsupported_object_kind = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path=f"/v1/rooms/{room_id}/query",
                body={
                    "query_id": "query:a16:unsupported-object",
                    "query_kind": "object.envelopes.list",
                    "request_id": "req:a16:unsupported-object",
                    "filters": {"object_kind": "memory_entity"},
                },
                headers={"x-request-id": "req:a16:unsupported-object"},
            )
        )
        invalid_cursor = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path=f"/v1/rooms/{room_id}/query",
                body={
                    "query_id": "query:a16:invalid-cursor",
                    "query_kind": "object.envelopes.list",
                    "request_id": "req:a16:invalid-cursor",
                    "filters": {"object_kind": "dataset"},
                    "cursor": "next-page",
                },
                headers={"x-request-id": "req:a16:invalid-cursor"},
            )
        )

        self.assertEqual(missing_room["status_code"], 404)
        self.assertEqual(mismatched_request["status_code"], 400)
        self.assertIn("payload.request_id", mismatched_request["json"]["detail"])
        self.assertEqual(unsupported_query_kind["status_code"], 400)
        self.assertIn("Unsupported query_kind", unsupported_query_kind["json"]["detail"])
        self.assertEqual(unsupported_object_kind["status_code"], 400)
        self.assertIn("Unsupported object kind", unsupported_object_kind["json"]["detail"])
        self.assertEqual(invalid_cursor["status_code"], 400)
        self.assertIn("cursor must be a non-negative integer string", invalid_cursor["json"]["detail"])

    def test_v1_query_writes_append_only_audit_chain(self) -> None:
        ingest_result = self._ingest_dataset(
            label="Query Audit Fixture",
            classification_level="personal",
            folder_name="query_audit_fixture",
            files={"note.txt": "alpha"},
        )
        room_id = ingest_result["dataset"]["room_id"]
        self._seed_room(room_id)
        app = create_app(self._settings_for("phase_a1_6.sqlite"))

        first = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path=f"/v1/rooms/{room_id}/query",
                body={
                    "query_id": "query:a16:audit:ok",
                    "query_kind": "object.envelopes.list",
                    "request_id": "req:a16:audit:ok",
                    "filters": {"object_kind": "dataset"},
                    "limit": 2,
                },
                headers={
                    "x-request-id": "req:a16:audit:ok",
                    "x-trace-id": "trace:a16:audit:ok",
                    "x-klone-principal": "owner:a16",
                    "x-klone-role": "owner",
                },
            )
        )
        second = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path=f"/v1/rooms/{room_id}/query",
                body={
                    "query_id": "query:a16:audit:error",
                    "query_kind": "object.envelopes.list",
                    "request_id": "req:a16:audit:error",
                    "filters": {"object_kind": "memory_entity"},
                },
                headers={
                    "x-request-id": "req:a16:audit:error",
                    "x-trace-id": "trace:a16:audit:error",
                    "x-klone-principal": "owner:a16",
                    "x-klone-role": "owner",
                },
            )
        )

        self.assertEqual(first["status_code"], 200)
        self.assertEqual(second["status_code"], 400)

        chain_rows = self.repository.list_control_plane_audit_chain(limit=10)
        query_rows = [row for row in chain_rows if row["event_type"] == "v1_query_read"]
        self.assertGreaterEqual(len(query_rows), 2)

        latest = query_rows[0]
        older = query_rows[1]
        self.assertEqual(latest["request_id"], "req:a16:audit:error")
        self.assertEqual(latest["trace_id"], "trace:a16:audit:error")
        self.assertEqual(latest["status_code"], 400)
        self.assertEqual(latest["route_path"], f"/v1/rooms/{room_id}/query")
        self.assertEqual(older["request_id"], "req:a16:audit:ok")
        self.assertEqual(older["status_code"], 200)
        self.assertEqual(latest["prev_event_hash"], older["event_hash"])

    def test_v1_capabilities_exposes_public_query_route(self) -> None:
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
        self.assertIn(
            "POST /v1/rooms/{room_id}/query is the first public read-only query route.",
            contracts["query-shell"]["notes"],
        )

    def test_v1_surface_contains_capabilities_object_get_and_query(self) -> None:
        v1_routes = {
            route.path: sorted(route.methods)
            for route in v1_router.routes
            if route.path.startswith("/v1")
        }
        self.assertEqual(
            v1_routes,
            {
                "/v1/capabilities": ["GET"],
                "/v1/rooms/{room_id}/objects/get": ["POST"],
                "/v1/rooms/{room_id}/query": ["POST"],
            },
        )

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
                "client": ("127.0.0.1", 50007),
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
