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


class Phase2E1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_constitution_route_returns_read_only_snapshot(self) -> None:
        app = create_app(self._settings_for("phase_2e_1.sqlite"))
        observed = asyncio.run(self._perform_request(app, method="GET", path="/api/constitution"))

        self.assertEqual(observed["status_code"], 200)
        payload = observed["json"]
        self.assertEqual(payload["profile_id"], "constitution:default")
        self.assertEqual(payload["layer_version"], "2e.1.read_only_shell")
        self.assertTrue(payload["read_only"])
        self.assertFalse(payload["routing_influence_enabled"])
        self.assertEqual(payload["parameter_count"], len(payload["parameters"]))
        self.assertEqual(payload["change_count"], len(payload["recent_changes"]))
        parameter_keys = {item["key"] for item in payload["parameters"]}
        self.assertIn("evidence_strictness", parameter_keys)
        self.assertIn("privacy_bias", parameter_keys)
        self.assertIn("No write path exists yet.", payload["warnings"][0])

    def test_v1_capabilities_expose_constitution_service_and_capability(self) -> None:
        app = create_app(self._settings_for("phase_2e_1_caps.sqlite"))
        observed = asyncio.run(self._perform_request(app, method="GET", path="/v1/capabilities"))

        self.assertEqual(observed["status_code"], 200)
        payload = observed["json"]
        service_ids = {item["id"] for item in payload["services"]}
        self.assertIn("constitution-service", service_ids)
        capability_map = {item["id"]: item for item in payload["capabilities"]}
        self.assertEqual(capability_map["constitution.snapshot.read"]["path"], "/api/constitution")
        self.assertEqual(capability_map["constitution.snapshot.read"]["methods"], ["GET"])
        self.assertTrue(capability_map["constitution.snapshot.read"]["read_only"])
        self.assertFalse(capability_map["constitution.snapshot.read"]["room_scoped"])

    def test_constitution_ui_copy_is_present(self) -> None:
        html = (PROJECT_ROOT / "src" / "klone" / "static" / "index.html").read_text(encoding="utf-8")
        js = (PROJECT_ROOT / "src" / "klone" / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("Constitution Layer", html)
        self.assertIn("Constitution Snapshot", js)
        self.assertIn("renderConstitution", js)
        self.assertIn("/api/constitution", js)

    async def _perform_request(
        self,
        app,
        *,
        method: str,
        path: str,
        body: dict[str, object] | None = None,
    ) -> dict[str, object]:
        async with app.router.lifespan_context(app):
            events: list[dict] = []
            body_bytes = json.dumps(body).encode("utf-8") if body is not None else b""
            headers = [(b"content-type", b"application/json")] if body is not None else []
            scope = {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": method,
                "scheme": "http",
                "path": path.split("?", 1)[0],
                "raw_path": path.split("?", 1)[0].encode("utf-8"),
                "query_string": path.split("?", 1)[1].encode("utf-8") if "?" in path else b"",
                "headers": headers,
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

    def _settings_for(self, database_name: str) -> Settings:
        database_path = self.root / database_name
        return Settings(
            app_name="Klone Phase 2E.1 Test",
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
