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
from klone.schemas import BlobMetadataRecord, DatasetIngestRequest  # noqa: E402
from klone.services import BlobService, ServiceContainer  # noqa: E402
from klone.v1_api import router as v1_router  # noqa: E402


class PhaseA13Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.repository = KloneRepository(self.root / "phase_a1_3.sqlite")
        self.repository.initialize()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_blob_service_projects_asset_rows_into_local_metadata_shell(self) -> None:
        self._ingest_dataset(
            label="Blob Shell Fixture",
            classification_level="personal",
            folder_name="blob_shell_fixture",
            files={"note.txt": "alpha"},
        )
        room_id = "restricted-room"
        services = ServiceContainer.build(self.repository)

        listed = services.blob.list_blob_metadata(room_id=room_id, limit=10)

        self.assertEqual(len(listed), 1)
        record = listed[0]
        self.assertIsInstance(record, BlobMetadataRecord)
        self.assertEqual(record.blob_id, BlobService.blob_id_for_asset(record.asset_id))
        self.assertEqual(record.linked_object_id, f"asset:{record.asset_id}")
        self.assertEqual(record.storage_kind, "local_filesystem")
        self.assertEqual(record.media_type, "text/plain")
        self.assertEqual(record.room_id, room_id)
        self.assertEqual(record.asset_kind, "text")
        self.assertEqual(record.relative_path, "note.txt")
        self.assertEqual(record.metadata["source"], "recursive_file_scan")

        fetched = services.blob.get_blob_metadata(blob_id=record.blob_id, room_id=room_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.model_dump(mode="json"), record.model_dump(mode="json"))

    def test_v1_capabilities_exposes_local_blob_shell_without_new_v1_routes(self) -> None:
        app = create_app(self._settings_for("phase_a1_3_app.sqlite"))
        observed = asyncio.run(self._perform_request(app, path="/v1/capabilities"))

        self.assertEqual(observed["status_code"], 200)
        payload = observed["json"]
        services = {item["id"]: item for item in payload["services"]}
        blob_service = services["blob-service"]
        self.assertEqual(blob_service["status"], "local_metadata_shell")
        self.assertEqual(blob_service["implementation"], "in_process_local_shell")
        self.assertIn("No public /v1 blobs upload or /v1/blobs/{blob_id}/meta route exists yet.", blob_service["notes"])

        capabilities = {item["id"]: item for item in payload["capabilities"]}
        self.assertEqual(capabilities["blob.metadata.list"]["path"], "/api/assets")
        self.assertEqual(capabilities["blob.metadata.detail"]["path"], "/api/assets/{asset_id}")
        self.assertEqual(capabilities["blob.metadata.list"]["status"], "available_via_asset_routes")
        self.assertEqual(capabilities["blob.metadata.detail"]["methods"], ["GET"])

    def test_v1_surface_remains_single_read_only_capabilities_route_after_a1_3(self) -> None:
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
                "client": ("127.0.0.1", 50003),
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
            app_name="Klone Phase A1.3 Test",
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
