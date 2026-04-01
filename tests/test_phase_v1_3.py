from __future__ import annotations

import asyncio
import base64
import json
import os
import sys
from pathlib import Path
import tempfile
import unittest

from PIL import Image, ImageDraw


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from klone.config import Settings  # noqa: E402
from klone.ingest import ingest_dataset  # noqa: E402
from klone.main import create_app  # noqa: E402
from klone.repository import KloneRepository  # noqa: E402
from klone.schemas import DatasetIngestRequest  # noqa: E402


class PhaseV13Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.database_path = self.root / "phase_v1_3.sqlite"
        self.repository = KloneRepository(self.database_path)
        self.repository.initialize()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_depth_map_endpoint_renders_deterministic_upload_result(self) -> None:
        image_path = self.root / "upload_depth.png"
        self._write_image(
            image_path,
            background="#ded7c8",
            shapes=lambda draw: (
                draw.rectangle((20, 36, 118, 220), fill="#33281b"),
                draw.ellipse((86, 18, 214, 146), fill="#5c95cf"),
                draw.line((18, 210, 236, 210), fill="#0e1718", width=10),
            ),
        )
        payload = {
            "image_data_url": self._data_url_for(image_path, mime_type="image/png"),
            "file_name": "upload_depth.png",
            "mime_type": "image/png",
        }
        app = create_app(self._settings_for(self.database_path.name))

        first = asyncio.run(
            self._perform_request(app, method="POST", path="/api/art/depth-map", body=payload)
        )
        second = asyncio.run(
            self._perform_request(app, method="POST", path="/api/art/depth-map", body=payload)
        )

        self.assertEqual(first["status_code"], 200)
        self.assertEqual(first["json"], second["json"])
        observed = first["json"]
        self.assertEqual(observed["depth_version"], "v1.3.read_only_2_5d_depth_map_shell")
        self.assertEqual(observed["source_mode"], "upload")
        self.assertEqual(observed["file_name"], "upload_depth.png")
        self.assertIsNone(observed["asset_id"])
        self.assertTrue(observed["original_data_url"].startswith("data:image/png;base64,"))
        self.assertTrue(observed["depth_map_data_url"].startswith("data:image/png;base64,"))
        self.assertTrue(observed["colorized_depth_data_url"].startswith("data:image/png;base64,"))
        self.assertIn("deterministic local 2.5D approximation", observed["notes"][0])

    def test_depth_map_endpoint_supports_existing_image_asset(self) -> None:
        fixture = self._ingest_visual_fixture(folder_name="v13_asset")
        app = create_app(self._settings_for(self.database_path.name))

        observed = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path="/api/art/depth-map",
                body={"asset_id": fixture["asset_id"]},
            )
        )

        self.assertEqual(observed["status_code"], 200)
        payload = observed["json"]
        self.assertEqual(payload["source_mode"], "asset")
        self.assertEqual(payload["asset_id"], fixture["asset_id"])
        self.assertEqual(payload["room_id"], fixture["room_id"])
        self.assertEqual(payload["classification_level"], "personal")
        self.assertEqual(payload["file_name"], "depth_subject.png")
        self.assertGreater(payload["depth_mean"], 0)

    def test_v1_capabilities_expose_depth_map_capability(self) -> None:
        app = create_app(self._settings_for("phase_v1_3_caps.sqlite"))
        observed = asyncio.run(self._perform_request(app, method="GET", path="/v1/capabilities"))

        self.assertEqual(observed["status_code"], 200)
        payload = observed["json"]
        capability_map = {item["id"]: item for item in payload["capabilities"]}
        self.assertEqual(capability_map["art.depth_map.render"]["path"], "/api/art/depth-map")
        self.assertEqual(capability_map["art.depth_map.render"]["methods"], ["POST"])
        self.assertTrue(capability_map["art.depth_map.render"]["read_only"])

    def test_depth_map_ui_copy_is_present(self) -> None:
        html = (PROJECT_ROOT / "src" / "klone" / "static" / "index.html").read_text(encoding="utf-8")
        js = (PROJECT_ROOT / "src" / "klone" / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("2.5D Depth Mapper", html)
        self.assertIn("/api/art/depth-map", js)
        self.assertIn("depth-map-drop-zone", js)
        self.assertIn("Use Selected Asset", js)

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
                "client": ("127.0.0.1", 50018),
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

    def _ingest_visual_fixture(self, *, folder_name: str) -> dict[str, object]:
        folder = self.root / folder_name
        folder.mkdir(parents=True, exist_ok=True)

        subject = folder / "depth_subject.png"
        self._write_image(
            subject,
            background="#c7d2d9",
            shapes=lambda draw: (
                draw.rectangle((28, 54, 132, 230), fill="#21150f"),
                draw.ellipse((98, 30, 224, 158), fill="#74a9e2"),
                draw.polygon([(14, 240), (100, 180), (200, 240)], fill="#5f6f42"),
            ),
        )

        base_timestamp = 1_700_100_000
        os.utime(subject, (base_timestamp, base_timestamp))

        request = DatasetIngestRequest(
            label=f"{folder_name} fixture",
            root_path=str(folder),
            collection="fixtures",
            classification_level="personal",
            description="Visual fixture for depth-map testing.",
        )
        ingest_result = ingest_dataset(self.repository, request)
        room_id = ingest_result["dataset"]["room_id"]
        asset = self.repository.list_assets(room_id=room_id, limit=8)[0]
        return {
            "room_id": room_id,
            "asset_id": asset["id"],
        }

    @staticmethod
    def _write_image(path: Path, *, background: str, shapes) -> None:
        image = Image.new("RGB", (256, 256), background)
        draw = ImageDraw.Draw(image)
        shapes(draw)
        image.save(path)

    @staticmethod
    def _data_url_for(path: Path, *, mime_type: str) -> str:
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"

    def _settings_for(self, database_name: str) -> Settings:
        database_path = self.root / database_name
        return Settings(
            app_name="Klone Phase V1.3 Test",
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
