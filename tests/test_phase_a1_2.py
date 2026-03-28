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
        self.assertEqual(blob_contract["route_readiness"], "metadata_only_no_public_upload")
        self.assertIn("No /v1 blobs upload route exists yet.", blob_contract["notes"])

    def test_v1_surface_remains_single_route_after_contract_registry_addition(self) -> None:
        v1_routes = {
            route.path: sorted(route.methods)
            for route in v1_router.routes
            if route.path.startswith("/v1")
        }
        self.assertEqual(v1_routes, {"/v1/capabilities": ["GET"]})

    async def _perform_request(self, app, *, path: str) -> dict[str, object]:
        async with app.router.lifespan_context(app):
            events: list[dict] = []
            scope = {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": "GET",
                "scheme": "http",
                "path": path,
                "raw_path": path.encode("utf-8"),
                "query_string": b"",
                "headers": [],
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
