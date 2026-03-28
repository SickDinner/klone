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


class PhaseG12Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.database_path = self.root / "phase_g1_2.sqlite"
        self.repository = KloneRepository(self.database_path)
        self.repository.initialize()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_ingest_run_manifest_history_persists_after_later_rescan(self) -> None:
        folder = self.root / "g12_history"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "one.txt").write_text("alpha", encoding="utf-8")
        (folder / "two.txt").write_text("beta", encoding="utf-8")

        request = DatasetIngestRequest(
            label="G12 History",
            root_path=str(folder),
            collection="fixtures",
            classification_level="personal",
            description="Manifest history fixture.",
        )

        first = ingest_dataset(self.repository, request)

        (folder / "one.txt").write_text("alpha updated", encoding="utf-8")
        (folder / "three.txt").write_text("gamma", encoding="utf-8")

        second = ingest_dataset(self.repository, request)

        app = create_app(self._settings_for("phase_g1_2.sqlite"))
        first_manifest = asyncio.run(
            self._perform_request(app, method="GET", path=f"/api/ingest/runs/{first['run']['id']}/manifest")
        )
        second_manifest = asyncio.run(
            self._perform_request(app, method="GET", path=f"/api/ingest/runs/{second['run']['id']}/manifest")
        )
        ingest_status = asyncio.run(
            self._perform_request(app, method="GET", path="/api/ingest/status?room_id=restricted-room")
        )

        self.assertEqual(first_manifest["status_code"], 200)
        self.assertEqual(second_manifest["status_code"], 200)
        self.assertEqual(ingest_status["status_code"], 200)
        self.assertTrue(ingest_status["json"]["latest_run"]["has_manifest"])

        first_payload = first_manifest["json"]
        second_payload = second_manifest["json"]

        self.assertEqual(first_payload["run"]["id"], first["run"]["id"])
        self.assertEqual(first_payload["run"]["new_assets"], 2)
        self.assertEqual(first_payload["run"]["updated_assets"], 0)
        self.assertEqual(first_payload["run"]["unchanged_assets"], 0)
        self.assertEqual(first_payload["total_size_bytes"], len("alpha") + len("beta"))
        first_samples = {item["relative_path"]: item for item in first_payload["sample_assets"]}
        self.assertEqual(first_samples["one.txt"]["planned_action"], "new")
        self.assertEqual(first_samples["two.txt"]["planned_action"], "new")

        self.assertEqual(second_payload["run"]["id"], second["run"]["id"])
        self.assertEqual(second_payload["run"]["new_assets"], 1)
        self.assertEqual(second_payload["run"]["updated_assets"], 1)
        self.assertEqual(second_payload["run"]["unchanged_assets"], 1)
        second_samples = {item["relative_path"]: item for item in second_payload["sample_assets"]}
        self.assertEqual(second_samples["one.txt"]["planned_action"], "updated")
        self.assertEqual(second_samples["two.txt"]["planned_action"], "unchanged")
        self.assertEqual(second_samples["three.txt"]["planned_action"], "new")

        first_breakdown = {item["asset_kind"]: item for item in first_payload["asset_kind_breakdown"]}
        second_breakdown = {item["asset_kind"]: item for item in second_payload["asset_kind_breakdown"]}
        self.assertEqual(first_breakdown["text"]["count"], 2)
        self.assertEqual(second_breakdown["text"]["count"], 3)

    def test_ingest_run_manifest_uses_summarize_surface_for_sandbox_room(self) -> None:
        ingest_result = self._ingest_dataset(
            label="G12 Sandbox",
            classification_level="restricted_bio",
            folder_name="g12_sandbox",
            files={"sample.txt": "dna-like"},
        )
        room_id = ingest_result["dataset"]["room_id"]
        self.assertEqual(room_id, "sandbox-room")
        asset_id = self.repository.list_assets(room_id=room_id, dataset_id=ingest_result["dataset"]["id"], limit=10)[0]["id"]

        app = create_app(self._settings_for("phase_g1_2.sqlite"))
        manifest = asyncio.run(
            self._perform_request(
                app,
                method="GET",
                path=f"/api/ingest/runs/{ingest_result['run']['id']}/manifest",
            )
        )
        asset_detail = asyncio.run(
            self._perform_request(app, method="GET", path=f"/api/assets/{asset_id}")
        )

        self.assertEqual(manifest["status_code"], 200)
        self.assertEqual(manifest["json"]["run"]["room_id"], "sandbox-room")
        self.assertTrue(manifest["json"]["run"]["has_manifest"])
        self.assertEqual(asset_detail["status_code"], 404)

    def test_ingest_run_manifest_missing_run_returns_404(self) -> None:
        app = create_app(self._settings_for("phase_g1_2.sqlite"))
        response = asyncio.run(
            self._perform_request(app, method="GET", path="/api/ingest/runs/9999/manifest")
        )
        self.assertEqual(response["status_code"], 404)
        self.assertIn("Ingest run 9999 was not found", response["json"]["detail"])

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
            app_name="Klone Phase G1.2 Test",
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
