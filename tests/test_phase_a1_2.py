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


class PhaseA12Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_v1_capabilities_exposes_contract_shell_registry(self) -> None:
        app = create_app(self._settings_for("phase_a1_2.sqlite"))
        observed = asyncio.run(self._perform_request(app, path="/v1/capabilities"))

        self.assertEqual(observed["status_code"], 200)
        payload = observed["json"]
        contracts = payload["contracts"]
        contract_ids = {item["id"] for item in contracts}

        self.assertEqual(
            contract_ids,
            {"object-shell", "query-shell", "change-shell", "blob-shell"},
        )
        for contract in contracts:
            self.assertEqual(contract["status"], "contract_shell")
            self.assertGreaterEqual(len(contract["fields"]), 6)
            self.assertIn("route_readiness", contract)

        blob_contract = next(item for item in contracts if item["id"] == "blob-shell")
        self.assertEqual(blob_contract["route_readiness"], "public_read_only_meta_available")
        self.assertIn("No /v1 blobs upload route exists yet.", blob_contract["notes"])

    def test_v1_capabilities_writes_append_only_control_plane_audit_chain(self) -> None:
        app = create_app(self._settings_for("phase_a1_2_audit.sqlite"))

        first = asyncio.run(
            self._perform_request(
                app,
                path="/v1/capabilities",
                headers={
                    "x-request-id": "req:a12-1",
                    "x-trace-id": "trace:a12-1",
                    "x-klone-principal": "owner:alpha",
                    "x-klone-role": "owner",
                },
            )
        )
        second = asyncio.run(
            self._perform_request(
                app,
                path="/v1/capabilities",
                headers={
                    "x-request-id": "req:a12-2",
                    "x-trace-id": "trace:a12-2",
                    "x-klone-principal": "owner:beta",
                    "x-klone-role": "owner",
                },
            )
        )

        self.assertEqual(first["status_code"], 200)
        self.assertEqual(second["status_code"], 200)

        app = create_app(self._settings_for("phase_a1_2_audit.sqlite"))
        chain_rows = asyncio.run(self._read_control_plane_chain(app))

        self.assertEqual(len(chain_rows), 2)

        latest, older = chain_rows[0], chain_rows[1]
        self.assertEqual(latest["request_id"], "req:a12-2")
        self.assertEqual(latest["trace_id"], "trace:a12-2")
        self.assertEqual(latest["principal"], "owner:beta")
        self.assertEqual(latest["actor_role"], "owner")
        self.assertEqual(latest["event_type"], "v1_capabilities_read")
        self.assertEqual(latest["route_path"], "/v1/capabilities")
        self.assertEqual(latest["status_code"], 200)
        self.assertEqual(latest["prev_event_hash"], older["event_hash"])
        self.assertNotEqual(latest["event_hash"], older["event_hash"])
        self.assertIsNone(older["prev_event_hash"])
        self.assertEqual(older["request_id"], "req:a12-1")

    def test_v1_surface_contains_blob_object_and_query_routes(self) -> None:
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
                "client": ("127.0.0.1", 50002),
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

    async def _read_control_plane_chain(self, app) -> list[dict[str, object]]:
        async with app.router.lifespan_context(app):
            return app.state.repository.list_control_plane_audit_chain(limit=10)

    def _settings_for(self, database_name: str) -> Settings:
        database_path = self.root / database_name
        return Settings(
            app_name="Klone Phase A1.2 Test",
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
