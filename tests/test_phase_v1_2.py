from __future__ import annotations

import asyncio
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


class PhaseV12Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.database_path = self.root / "phase_v1_2.sqlite"
        self.repository = KloneRepository(self.database_path)
        self.repository.initialize()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_art_compare_endpoint_returns_deterministic_room_scoped_comparison(self) -> None:
        fixture = self._ingest_visual_fixture(folder_name="v12_compare")
        room_id = fixture["room_id"]
        asset_ids = fixture["asset_ids"]

        app = create_app(self._settings_for(self.database_path.name))
        path = (
            "/api/art/assets/compare"
            f"?room_id={room_id}"
            f"&asset_id={asset_ids['late']}"
            f"&asset_id={asset_ids['early']}"
            f"&asset_id={asset_ids['mid']}"
        )

        first = asyncio.run(self._perform_request(app, method="GET", path=path))
        second = asyncio.run(self._perform_request(app, method="GET", path=path))

        self.assertEqual(first["status_code"], 200)
        self.assertEqual(first["json"], second["json"])

        payload = first["json"]
        self.assertEqual(payload["comparison_version"], "v1.2.formal_image_metrics_comparison")
        self.assertEqual(payload["analysis_version"], "v1.1.formal_image_metrics")
        self.assertEqual(payload["room_id"], room_id)
        self.assertEqual(payload["ordering_basis"], "fs_modified_at")
        self.assertEqual(payload["requested_asset_ids"], [asset_ids["late"], asset_ids["early"], asset_ids["mid"]])
        self.assertEqual(payload["ordered_asset_ids"], [asset_ids["early"], asset_ids["mid"], asset_ids["late"]])
        self.assertEqual(payload["asset_count"], 3)
        self.assertEqual([item["position"] for item in payload["compared_assets"]], [1, 2, 3])
        self.assertEqual(
            [item["asset_id"] for item in payload["compared_assets"]],
            [asset_ids["early"], asset_ids["mid"], asset_ids["late"]],
        )
        self.assertEqual(
            [item["fs_modified_at"] for item in payload["compared_assets"]],
            sorted(item["fs_modified_at"] for item in payload["compared_assets"]),
        )
        deltas = {item["metric_name"]: item for item in payload["metric_deltas"]}
        self.assertIn("brightness_mean", deltas)
        self.assertEqual(deltas["brightness_mean"]["start_asset_id"], asset_ids["early"])
        self.assertEqual(deltas["brightness_mean"]["end_asset_id"], asset_ids["late"])
        self.assertNotEqual(deltas["brightness_mean"]["delta"], 0.0)
        self.assertIn("No OCR, embeddings, clustering", payload["notes"][2])

    def test_art_compare_requires_image_assets_only(self) -> None:
        fixture = self._ingest_visual_fixture(folder_name="v12_non_image")
        room_id = fixture["room_id"]
        asset_ids = fixture["asset_ids"]

        app = create_app(self._settings_for(self.database_path.name))
        path = (
            "/api/art/assets/compare"
            f"?room_id={room_id}"
            f"&asset_id={asset_ids['early']}"
            f"&asset_id={asset_ids['notes']}"
        )

        observed = asyncio.run(self._perform_request(app, method="GET", path=path))

        self.assertEqual(observed["status_code"], 400)
        self.assertIn("image assets only", observed["json"]["detail"])

    def test_art_compare_blocks_cross_room_assets(self) -> None:
        personal = self._ingest_visual_fixture(folder_name="v12_personal", classification_level="personal")
        intimate = self._ingest_visual_fixture(folder_name="v12_intimate", classification_level="intimate")

        app = create_app(self._settings_for(self.database_path.name))
        path = (
            "/api/art/assets/compare"
            f"?room_id={personal['room_id']}"
            f"&asset_id={personal['asset_ids']['early']}"
            f"&asset_id={intimate['asset_ids']['early']}"
        )

        observed = asyncio.run(self._perform_request(app, method="GET", path=path))

        self.assertEqual(observed["status_code"], 404)
        self.assertIn(personal["room_id"], observed["json"]["detail"])

    def test_v1_capabilities_expose_art_comparison_capability(self) -> None:
        app = create_app(self._settings_for("phase_v1_2_caps.sqlite"))
        observed = asyncio.run(self._perform_request(app, method="GET", path="/v1/capabilities"))

        self.assertEqual(observed["status_code"], 200)
        payload = observed["json"]
        capability_map = {item["id"]: item for item in payload["capabilities"]}
        self.assertEqual(capability_map["art.asset.compare.read"]["path"], "/api/art/assets/compare")
        self.assertEqual(capability_map["art.asset.compare.read"]["methods"], ["GET"])
        self.assertTrue(capability_map["art.asset.compare.read"]["read_only"])
        self.assertTrue(capability_map["art.asset.compare.read"]["room_scoped"])

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

    def _ingest_visual_fixture(
        self,
        *,
        folder_name: str,
        classification_level: str = "personal",
    ) -> dict[str, object]:
        folder = self.root / folder_name
        folder.mkdir(parents=True, exist_ok=True)

        early = folder / "draw_early.png"
        mid = folder / "draw_mid.png"
        late = folder / "draw_late.png"

        self._write_image(
            early,
            background="white",
            shapes=lambda draw: draw.rectangle((8, 8, 60, 220), fill="black"),
        )
        self._write_image(
            mid,
            background="#d0d0d0",
            shapes=lambda draw: draw.line((20, 30, 140, 210), fill="black", width=8),
        )
        self._write_image(
            late,
            background="#808080",
            shapes=lambda draw: (
                draw.rectangle((16, 32, 120, 208), outline="black", width=10),
                draw.ellipse((72, 48, 144, 120), fill="black"),
            ),
        )

        base_timestamp = 1_700_000_000
        os.utime(early, (base_timestamp, base_timestamp))
        os.utime(mid, (base_timestamp + 60, base_timestamp + 60))
        os.utime(late, (base_timestamp + 120, base_timestamp + 120))

        notes = folder / "notes.txt"
        notes.write_text("not an image asset", encoding="utf-8")
        os.utime(notes, (base_timestamp + 180, base_timestamp + 180))

        request = DatasetIngestRequest(
            label=f"{folder_name} fixture",
            root_path=str(folder),
            collection="fixtures",
            classification_level=classification_level,
            description="Visual fixture for bounded art comparison.",
        )
        ingest_result = ingest_dataset(self.repository, request)
        room_id = ingest_result["dataset"]["room_id"]

        assets = {
            asset["file_name"]: asset
            for asset in self.repository.list_assets(room_id=room_id, limit=20)
        }
        return {
            "room_id": room_id,
            "asset_ids": {
                "early": assets["draw_early.png"]["id"],
                "mid": assets["draw_mid.png"]["id"],
                "late": assets["draw_late.png"]["id"],
                "notes": assets["notes.txt"]["id"],
            },
        }

    @staticmethod
    def _write_image(path: Path, *, background: str, shapes) -> None:
        image = Image.new("RGB", (160, 240), background)
        draw = ImageDraw.Draw(image)
        shapes(draw)
        image.save(path)

    def _settings_for(self, database_name: str) -> Settings:
        database_path = self.root / database_name
        return Settings(
            app_name="Klone Phase V1.2 Test",
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
