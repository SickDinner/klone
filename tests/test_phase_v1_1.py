from __future__ import annotations

import asyncio
import json
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


class PhaseV11Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.database_path = self.root / "phase_v1_1.sqlite"
        self.repository = KloneRepository(self.database_path)
        self.repository.initialize()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_art_metrics_endpoint_returns_formal_metrics_for_image_asset(self) -> None:
        ingest_result = self._ingest_visual_fixture()
        room_id = ingest_result["dataset"]["room_id"]
        image_asset = next(
            asset
            for asset in self.repository.list_assets(room_id=room_id, limit=20)
            if asset["file_name"] == "drawing.png"
        )

        app = create_app(self._settings_for("phase_v1_1.sqlite"))
        observed = asyncio.run(
            self._perform_request(app, method="GET", path=f"/api/art/assets/{image_asset['id']}/metrics")
        )

        self.assertEqual(observed["status_code"], 200)
        payload = observed["json"]
        self.assertEqual(payload["analysis_version"], "v1.1.formal_image_metrics")
        self.assertEqual(payload["asset_id"], image_asset["id"])
        self.assertEqual(payload["asset_kind"], "image")
        self.assertEqual(payload["orientation"], "portrait")
        self.assertEqual(payload["width_px"], 160)
        self.assertEqual(payload["height_px"], 240)
        self.assertEqual(payload["sample_width_px"], 85)
        self.assertEqual(payload["sample_height_px"], 128)
        self.assertGreater(payload["edge_density"], 0.02)
        self.assertGreater(payload["ink_coverage_ratio"], 0.1)
        self.assertLess(payload["center_of_mass_x"], 0.5)
        self.assertTrue(0.0 <= payload["symmetry_vertical"] <= 1.0)
        self.assertTrue(0.0 <= payload["symmetry_horizontal"] <= 1.0)
        self.assertIn("downscaled_for_analysis", payload["warnings"])
        self.assertIn("Formal image metrics only", payload["notes"][0])

    def test_art_metrics_reject_non_image_assets(self) -> None:
        ingest_result = self._ingest_visual_fixture()
        room_id = ingest_result["dataset"]["room_id"]
        text_asset = next(
            asset
            for asset in self.repository.list_assets(room_id=room_id, limit=20)
            if asset["file_name"] == "notes.txt"
        )

        app = create_app(self._settings_for("phase_v1_1.sqlite"))
        observed = asyncio.run(
            self._perform_request(app, method="GET", path=f"/api/art/assets/{text_asset['id']}/metrics")
        )

        self.assertEqual(observed["status_code"], 400)
        self.assertIn("image assets only", observed["json"]["detail"])

    def test_v1_capabilities_expose_art_service_and_metric_capability(self) -> None:
        app = create_app(self._settings_for("phase_v1_1_caps.sqlite"))
        observed = asyncio.run(self._perform_request(app, method="GET", path="/v1/capabilities"))

        self.assertEqual(observed["status_code"], 200)
        payload = observed["json"]
        service_ids = {item["id"] for item in payload["services"]}
        self.assertIn("art-lab-service", service_ids)
        capability_ids = {item["id"] for item in payload["capabilities"]}
        self.assertIn("art.asset.metrics.read", capability_ids)

    def test_art_metrics_ui_copy_is_present(self) -> None:
        html = (PROJECT_ROOT / "src" / "klone" / "static" / "index.html").read_text(encoding="utf-8")
        js = (PROJECT_ROOT / "src" / "klone" / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("Art Metrics", html)
        self.assertIn("renderArtMetrics", js)
        self.assertIn("/api/art/assets/", js)

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

    def _ingest_visual_fixture(self) -> dict[str, object]:
        folder = self.root / "v1_visual"
        folder.mkdir(parents=True, exist_ok=True)

        image = Image.new("RGB", (160, 240), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 54, 239), fill="black")
        draw.line((55, 20, 140, 210), fill="black", width=6)
        draw.ellipse((90, 40, 145, 95), outline="black", width=4)
        image.save(folder / "drawing.png")

        (folder / "notes.txt").write_text("visual metadata fixture", encoding="utf-8")

        request = DatasetIngestRequest(
            label="V11 Visual Fixture",
            root_path=str(folder),
            collection="fixtures",
            classification_level="personal",
            description="Visual fixture for art metrics.",
        )
        return ingest_dataset(self.repository, request)

    def _settings_for(self, database_name: str) -> Settings:
        database_path = self.root / database_name
        return Settings(
            app_name="Klone Phase V1.1 Test",
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
