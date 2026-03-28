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
from klone.repository import KloneRepository  # noqa: E402
from klone.schemas import DatasetIngestRequest  # noqa: E402
from klone.v1_api import router as v1_router  # noqa: E402


class PhaseA18Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.database_path = self.root / "phase_a1_8.sqlite"
        self.repository = KloneRepository(self.database_path)
        self.repository.initialize()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_v1_query_supports_audit_preview_with_stable_pagination_and_filters(self) -> None:
        first = self._ingest_dataset(
            label="A18 Audit One",
            classification_level="personal",
            folder_name="a18_audit_one",
            files={"one.txt": "alpha"},
        )
        second = self._ingest_dataset(
            label="A18 Audit Two",
            classification_level="personal",
            folder_name="a18_audit_two",
            files={"two.txt": "beta"},
        )
        self.assertEqual(first["dataset"]["room_id"], second["dataset"]["room_id"])
        room_id = first["dataset"]["room_id"]

        expected_first_page = self.repository.list_audit_events(room_id=room_id, limit=2, offset=0)
        expected_second_page = self.repository.list_audit_events(room_id=room_id, limit=2, offset=2)
        expected_completed = self.repository.list_audit_events(
            room_id=room_id,
            limit=10,
            offset=0,
            event_type="ingest_completed",
            target_type="ingest_run",
        )

        app = create_app(self._settings_for("phase_a1_8.sqlite"))
        first_page = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path=f"/v1/rooms/{room_id}/query",
                body={"query_kind": "audit_preview", "limit": 2, "offset": 0},
                headers={"x-request-id": "req:a18-audit-a"},
            )
        )
        first_page_repeat = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path=f"/v1/rooms/{room_id}/query",
                body={"query_kind": "audit_preview", "limit": 2, "offset": 0},
                headers={"x-request-id": "req:a18-audit-a-repeat"},
            )
        )
        second_page = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path=f"/v1/rooms/{room_id}/query",
                body={"query_kind": "audit_preview", "limit": 2, "offset": 2},
                headers={"x-request-id": "req:a18-audit-b"},
            )
        )
        filtered_page = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path=f"/v1/rooms/{room_id}/query",
                body={
                    "query_kind": "audit_preview",
                    "limit": 10,
                    "offset": 0,
                    "event_type": "ingest_completed",
                    "target_type": "ingest_run",
                },
                headers={"x-request-id": "req:a18-audit-c"},
            )
        )

        self.assertEqual(first_page["status_code"], 200)
        self.assertEqual(first_page_repeat["status_code"], 200)
        self.assertEqual(second_page["status_code"], 200)
        self.assertEqual(filtered_page["status_code"], 200)
        self.assertEqual(first_page["json"]["backing_routes"], ["/api/audit"])
        self.assertEqual(first_page["json"]["results"], first_page_repeat["json"]["results"])
        self.assertEqual([item["id"] for item in first_page["json"]["results"]], [row["id"] for row in expected_first_page])
        self.assertEqual([item["id"] for item in second_page["json"]["results"]], [row["id"] for row in expected_second_page])
        self.assertEqual([item["id"] for item in filtered_page["json"]["results"]], [row["id"] for row in expected_completed])
        self.assertTrue(all(item["room_id"] == room_id for item in filtered_page["json"]["results"]))
        self.assertTrue(all(item["event_type"] == "ingest_completed" for item in filtered_page["json"]["results"]))
        self.assertTrue(all(item["target_type"] == "ingest_run" for item in filtered_page["json"]["results"]))

    def test_v1_query_audit_preview_uses_summarize_permission(self) -> None:
        ingest_result = self._ingest_dataset(
            label="A18 Sandbox Audit",
            classification_level="restricted_bio",
            folder_name="a18_sandbox_audit",
            files={"sandbox.txt": "alpha"},
        )
        room_id = ingest_result["dataset"]["room_id"]
        self.assertEqual(room_id, "sandbox-room")

        app = create_app(self._settings_for("phase_a1_8.sqlite"))
        audit_preview = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path=f"/v1/rooms/{room_id}/query",
                body={"query_kind": "audit_preview", "limit": 10, "offset": 0},
                headers={"x-request-id": "req:a18-sandbox-audit"},
            )
        )
        memory_query = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path=f"/v1/rooms/{room_id}/query",
                body={"query_kind": "memory_events", "limit": 10, "offset": 0},
                headers={"x-request-id": "req:a18-sandbox-memory"},
            )
        )

        self.assertEqual(audit_preview["status_code"], 200)
        self.assertEqual(memory_query["status_code"], 403)
        self.assertTrue(all(item["room_id"] == room_id for item in audit_preview["json"]["results"]))
        self.assertIn("outside the current room policy", memory_query["json"]["detail"])

    def test_v1_query_audit_preview_blocks_mismatched_filter_shape(self) -> None:
        ingest_result = self._ingest_dataset(
            label="A18 Invalid Audit",
            classification_level="personal",
            folder_name="a18_invalid_audit",
            files={"note.txt": "alpha"},
        )
        room_id = ingest_result["dataset"]["room_id"]

        app = create_app(self._settings_for("phase_a1_8.sqlite"))
        invalid = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path=f"/v1/rooms/{room_id}/query",
                body={"query_kind": "audit_preview", "status": "active"},
                headers={"x-request-id": "req:a18-invalid"},
            )
        )

        self.assertEqual(invalid["status_code"], 400)
        self.assertIn("status is only supported for memory_events and memory_episodes queries", invalid["json"]["detail"])

    def test_v1_capabilities_and_route_surface_expose_a18_query_backing(self) -> None:
        ingest_result = self._ingest_dataset(
            label="A18 Capability Audit",
            classification_level="personal",
            folder_name="a18_capability_audit",
            files={"note.txt": "alpha"},
        )
        room_id = ingest_result["dataset"]["room_id"]
        app = create_app(self._settings_for("phase_a1_8.sqlite"))

        query_response = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path=f"/v1/rooms/{room_id}/query",
                body={"query_kind": "audit_preview", "limit": 5, "offset": 0},
                headers={
                    "x-request-id": "req:a18-1",
                    "x-trace-id": "trace:a18-1",
                    "x-klone-principal": "owner:a18",
                    "x-klone-role": "owner",
                },
            )
        )
        capabilities = asyncio.run(self._perform_request(app, method="GET", path="/v1/capabilities"))

        self.assertEqual(query_response["status_code"], 200)
        self.assertEqual(capabilities["status_code"], 200)

        capability_map = {item["id"]: item for item in capabilities["json"]["capabilities"]}
        self.assertEqual(capability_map["v1.query.read"]["path"], "/v1/rooms/{room_id}/query")
        self.assertEqual(capability_map["v1.query.read"]["methods"], ["POST"])
        self.assertIn("audit preview", capability_map["v1.query.read"]["description"])

        contract_map = {item["id"]: item for item in capabilities["json"]["contracts"]}
        self.assertEqual(contract_map["query-shell"]["route_readiness"], "public_read_only_query_available")
        self.assertEqual(
            contract_map["query-shell"]["backing_routes"],
            ["/v1/rooms/{room_id}/query", "/api/audit", "/api/memory/events", "/api/memory/episodes"],
        )

        chain_rows = self.repository.list_control_plane_audit_chain(limit=10)
        query_rows = [row for row in chain_rows if row["event_type"] == "v1_query_read"]
        self.assertGreaterEqual(len(query_rows), 1)
        self.assertEqual(query_rows[0]["request_id"], "req:a18-1")
        self.assertEqual(query_rows[0]["status_code"], 200)
        self.assertEqual(query_rows[0]["route_path"], f"/v1/rooms/{room_id}/query")

        v1_routes = {
            route.path: sorted(route.methods)
            for route in v1_router.routes
            if route.path.startswith("/v1")
        }
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
                "client": ("127.0.0.1", 50010),
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

    def _settings_for(self, database_name: str) -> Settings:
        database_path = self.root / database_name
        return Settings(
            app_name="Klone Phase A1.8 Test",
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
