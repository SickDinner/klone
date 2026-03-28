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


class PhaseG11Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.database_path = self.root / "phase_g1_1.sqlite"
        self.repository = KloneRepository(self.database_path)
        self.repository.initialize()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_ingest_preflight_predicts_run_counts_and_duplicate_samples(self) -> None:
        canonical_result = self._ingest_dataset(
            label="G11 Canonical",
            classification_level="personal",
            folder_name="g11_canonical",
            files={"canon.txt": "shared duplicate"},
        )
        target_folder = self.root / "g11_target"
        target_folder.mkdir(parents=True, exist_ok=True)
        (target_folder / "keep.txt").write_text("stable", encoding="utf-8")
        (target_folder / "change.txt").write_text("old value", encoding="utf-8")

        initial_request = DatasetIngestRequest(
            label="G11 Target",
            root_path=str(target_folder),
            collection="fixtures",
            classification_level="personal",
            description="Target dataset for preflight alignment.",
        )
        first_ingest = ingest_dataset(self.repository, initial_request)
        target_dataset_id = first_ingest["dataset"]["id"]

        (target_folder / "change.txt").write_text("new value", encoding="utf-8")
        (target_folder / "same.txt").write_text("shared duplicate", encoding="utf-8")

        app = create_app(self._settings_for("phase_g1_1.sqlite"))
        response = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path="/api/ingest/preflight?sample_limit=8",
                body=initial_request.model_dump(mode="json"),
            )
        )
        self.assertEqual(response["status_code"], 200)
        payload = response["json"]

        self.assertEqual(payload["room_id"], canonical_result["dataset"]["room_id"])
        self.assertEqual(payload["existing_dataset_id"], target_dataset_id)
        self.assertTrue(payload["can_start_ingest"])
        self.assertEqual(payload["files_discovered"], 3)
        self.assertEqual(payload["planned_new_assets"], 1)
        self.assertEqual(payload["planned_updated_assets"], 1)
        self.assertEqual(payload["planned_unchanged_assets"], 1)
        self.assertEqual(payload["duplicates_detected"], 1)
        self.assertEqual(payload["classification_guard"]["decision"], "allowed")
        self.assertEqual(payload["access_guard"]["decision"], "allowed")

        sample_by_path = {
            item["relative_path"]: item
            for item in payload["sample_assets"]
        }
        self.assertEqual(sample_by_path["keep.txt"]["planned_action"], "unchanged")
        self.assertEqual(sample_by_path["change.txt"]["planned_action"], "updated")
        self.assertEqual(sample_by_path["same.txt"]["planned_action"], "new")
        self.assertEqual(sample_by_path["same.txt"]["dedup_status"], "duplicate")
        self.assertIsNotNone(sample_by_path["same.txt"]["canonical_asset_id"])
        self.assertEqual(sample_by_path["same.txt"]["canonical_dataset_label"], "G11 Canonical")
        self.assertEqual(sample_by_path["same.txt"]["canonical_relative_path"], "canon.txt")

        breakdown = {item["asset_kind"]: item for item in payload["asset_kind_breakdown"]}
        self.assertEqual(breakdown["text"]["count"], 3)

        second_ingest = ingest_dataset(self.repository, initial_request)
        self.assertEqual(second_ingest["run"]["new_assets"], payload["planned_new_assets"])
        self.assertEqual(second_ingest["run"]["updated_assets"], payload["planned_updated_assets"])
        self.assertEqual(second_ingest["run"]["unchanged_assets"], payload["planned_unchanged_assets"])
        self.assertEqual(second_ingest["run"]["duplicates_detected"], payload["duplicates_detected"])

    def test_ingest_preflight_surfaces_requires_approval_without_blocking_preview(self) -> None:
        folder = self.root / "g11_intimate"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "note.txt").write_text("private", encoding="utf-8")
        request = DatasetIngestRequest(
            label="G11 Intimate",
            root_path=str(folder),
            collection="fixtures",
            classification_level="intimate",
            description="Intimate dataset preview.",
        )

        app = create_app(self._settings_for("phase_g1_1.sqlite"))
        response = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path="/api/ingest/preflight",
                body=request.model_dump(mode="json"),
            )
        )

        self.assertEqual(response["status_code"], 200)
        payload = response["json"]
        self.assertEqual(payload["room_id"], "sealed-room")
        self.assertFalse(payload["can_start_ingest"])
        self.assertEqual(payload["classification_guard"]["decision"], "allowed")
        self.assertEqual(payload["access_guard"]["decision"], "requires_approval")
        self.assertEqual(payload["files_discovered"], 1)
        self.assertIn("outside the current room policy", payload["warnings"][-1])

    def test_ingest_preflight_missing_root_returns_404(self) -> None:
        request = DatasetIngestRequest(
            label="Missing Root",
            root_path=str(self.root / "does_not_exist"),
            collection="fixtures",
            classification_level="personal",
            description="Missing root case.",
        )
        app = create_app(self._settings_for("phase_g1_1.sqlite"))
        response = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path="/api/ingest/preflight",
                body=request.model_dump(mode="json"),
            )
        )
        self.assertEqual(response["status_code"], 404)
        self.assertIn("Dataset root does not exist", response["json"]["detail"])

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
            app_name="Klone Phase G1.1 Test",
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
