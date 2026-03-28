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
from klone.main import create_app  # noqa: E402
from klone.v1_api import router as v1_router  # noqa: E402


class PhaseA11Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_v1_capabilities_returns_request_context_and_service_seams(self) -> None:
        app = create_app(self._settings_for("phase_a1_1.sqlite"))
        observed = asyncio.run(
            self._perform_request(
                app,
                path="/v1/capabilities",
                headers={
                    "x-request-id": "req:test-a11",
                    "x-trace-id": "trace:test-a11",
                    "x-klone-principal": "owner:tester",
                    "x-klone-role": "owner",
                },
            )
        )

        self.assertEqual(observed["status_code"], 200)
        self.assertEqual(observed["headers"]["x-request-id"], "req:test-a11")
        self.assertEqual(observed["headers"]["x-trace-id"], "trace:test-a11")
        self.assertEqual(observed["headers"]["x-klone-principal"], "owner:tester")
        self.assertEqual(observed["headers"]["x-klone-role"], "owner")

        payload = observed["json"]
        self.assertEqual(payload["api_version"], "v1")
        self.assertEqual(payload["request_context"]["request_id"], "req:test-a11")
        self.assertEqual(payload["request_context"]["trace_id"], "trace:test-a11")
        self.assertEqual(payload["request_context"]["principal"], "owner:tester")
        self.assertEqual(payload["request_context"]["actor_role"], "owner")

        service_ids = {item["id"] for item in payload["services"]}
        self.assertTrue(
            {"memory-facade", "policy-service", "audit-service", "blob-service"}.issubset(service_ids),
        )

        capability_ids = {item["id"] for item in payload["capabilities"]}
        self.assertIn("v1.capabilities.read", capability_ids)
        self.assertIn("memory.context.package", capability_ids)
        self.assertIn("memory.context.answer", capability_ids)
        self.assertIn("policy.rooms.read", capability_ids)

        module_ids = {item["id"] for item in payload["module_registry"]}
        self.assertIn("mission-control", module_ids)
        self.assertIn("memory-core", module_ids)

    def test_request_context_headers_are_added_to_existing_api_routes(self) -> None:
        app = create_app(self._settings_for("phase_a1_1_headers.sqlite"))
        observed = asyncio.run(self._perform_request(app, path="/api/health"))

        self.assertEqual(observed["status_code"], 200)
        self.assertTrue(observed["headers"]["x-request-id"].startswith("req:"))
        self.assertTrue(observed["headers"]["x-trace-id"].startswith("trace:"))
        self.assertEqual(observed["headers"]["x-klone-principal"], "owner")
        self.assertEqual(observed["headers"]["x-klone-role"], "owner")
        self.assertEqual(observed["json"]["status"], "ok")

    def test_v1_surface_remains_single_read_only_capabilities_route(self) -> None:
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
            },
        )

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
                "client": ("127.0.0.1", 50001),
                "server": ("testserver", 80),
                "app": app,
            }

            async def receive():
                return {"type": "http.request", "body": b"", "more_body": False}

            async def send(message):
                events.append(message)

            await app(scope, receive, send)

            response_start = next(item for item in events if item["type"] == "http.response.start")
            response_headers = {
                key.decode("utf-8").lower(): value.decode("utf-8")
                for key, value in response_start["headers"]
            }
            response_body = b"".join(
                item.get("body", b"")
                for item in events
                if item["type"] == "http.response.body"
            )
            return {
                "status_code": response_start["status"],
                "headers": response_headers,
                "json": json.loads(response_body.decode("utf-8")),
            }

    def _settings_for(self, database_name: str) -> Settings:
        database_path = self.root / database_name
        return Settings(
            app_name="Klone Phase A1.1 Test",
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
