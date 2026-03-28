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
from klone.services import ServiceContainer  # noqa: E402
from klone.v1_api import router as v1_router  # noqa: E402


class PhaseA17Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.database_path = self.root / "phase_a1_7.sqlite"
        self.repository = KloneRepository(self.database_path)
        self.repository.initialize()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_v1_blob_meta_returns_room_scoped_asset_backed_metadata(self) -> None:
        ingest_result = self._ingest_dataset(
            label="Blob Meta Fixture",
            classification_level="personal",
            folder_name="blob_meta_fixture",
            files={"note.txt": "alpha"},
        )
        room_id = ingest_result["dataset"]["room_id"]
        blob = ServiceContainer.build(self.repository).blob.list_blob_metadata(room_id=room_id, limit=10)[0]

        app = create_app(self._settings_for("phase_a1_7.sqlite"))
        observed = asyncio.run(
            self._perform_request(
                app,
                method="GET",
                path=f"/v1/rooms/{room_id}/blobs/{blob.blob_id}/meta",
                headers={"x-request-id": "req:a17-meta", "x-trace-id": "trace:a17-meta"},
            )
        )

        self.assertEqual(observed["status_code"], 200)
        payload = observed["json"]
        self.assertEqual(payload["room_id"], room_id)
        self.assertEqual(payload["blob"]["blob_id"], blob.blob_id)
        self.assertEqual(payload["blob"]["linked_object_id"], blob.linked_object_id)
        self.assertEqual(payload["blob"]["asset_id"], blob.asset_id)
        self.assertEqual(payload["blob"]["dataset_id"], ingest_result["dataset"]["id"])
        self.assertEqual(payload["blob"]["relative_path"], "note.txt")
        self.assertEqual(payload["blob"]["storage_kind"], "local_filesystem")
        self.assertEqual(payload["blob"]["room_id"], room_id)

    def test_v1_blob_meta_blocks_wrong_room_and_invalid_blob_id(self) -> None:
        restricted = self._ingest_dataset(
            label="Restricted Blob Meta",
            classification_level="personal",
            folder_name="restricted_blob_meta",
            files={"restricted.txt": "alpha"},
        )
        public = self._ingest_dataset(
            label="Public Blob Meta",
            classification_level="public",
            folder_name="public_blob_meta",
            files={"public.txt": "beta"},
        )
        restricted_room = restricted["dataset"]["room_id"]
        public_room = public["dataset"]["room_id"]
        blob = ServiceContainer.build(self.repository).blob.list_blob_metadata(room_id=restricted_room, limit=10)[0]

        app = create_app(self._settings_for("phase_a1_7.sqlite"))
        wrong_room = asyncio.run(
            self._perform_request(
                app,
                method="GET",
                path=f"/v1/rooms/{public_room}/blobs/{blob.blob_id}/meta",
                headers={"x-request-id": "req:a17-wrong-room"},
            )
        )
        invalid = asyncio.run(
            self._perform_request(
                app,
                method="GET",
                path=f"/v1/rooms/{restricted_room}/blobs/not-a-blob-id/meta",
                headers={"x-request-id": "req:a17-invalid"},
            )
        )

        self.assertEqual(wrong_room["status_code"], 404)
        self.assertIn("was not found", wrong_room["json"]["detail"])
        self.assertEqual(invalid["status_code"], 400)
        self.assertIn("blob:asset", invalid["json"]["detail"])

    def test_v1_blob_meta_writes_audit_chain_and_capabilities(self) -> None:
        ingest_result = self._ingest_dataset(
            label="Blob Audit Fixture",
            classification_level="personal",
            folder_name="blob_audit_fixture",
            files={"note.txt": "alpha"},
        )
        room_id = ingest_result["dataset"]["room_id"]
        blob = ServiceContainer.build(self.repository).blob.list_blob_metadata(room_id=room_id, limit=10)[0]
        app = create_app(self._settings_for("phase_a1_7.sqlite"))

        ok_response = asyncio.run(
            self._perform_request(
                app,
                method="GET",
                path=f"/v1/rooms/{room_id}/blobs/{blob.blob_id}/meta",
                headers={
                    "x-request-id": "req:a17-1",
                    "x-trace-id": "trace:a17-1",
                    "x-klone-principal": "owner:a17",
                    "x-klone-role": "owner",
                },
            )
        )
        invalid_response = asyncio.run(
            self._perform_request(
                app,
                method="GET",
                path=f"/v1/rooms/{room_id}/blobs/not-a-blob-id/meta",
                headers={
                    "x-request-id": "req:a17-2",
                    "x-trace-id": "trace:a17-2",
                    "x-klone-principal": "owner:a17",
                    "x-klone-role": "owner",
                },
            )
        )
        capabilities = asyncio.run(self._perform_request(app, method="GET", path="/v1/capabilities"))

        self.assertEqual(ok_response["status_code"], 200)
        self.assertEqual(invalid_response["status_code"], 400)
        self.assertEqual(capabilities["status_code"], 200)

        capability_map = {item["id"]: item for item in capabilities["json"]["capabilities"]}
        self.assertEqual(
            capability_map["v1.blobs.meta.read"]["path"],
            "/v1/rooms/{room_id}/blobs/{blob_id}/meta",
        )
        self.assertEqual(capability_map["v1.blobs.meta.read"]["methods"], ["GET"])
        self.assertTrue(capability_map["v1.blobs.meta.read"]["read_only"])
        self.assertTrue(capability_map["v1.blobs.meta.read"]["room_scoped"])

        contract_map = {item["id"]: item for item in capabilities["json"]["contracts"]}
        self.assertEqual(contract_map["blob-shell"]["route_readiness"], "public_read_only_meta_available")
        self.assertEqual(
            contract_map["blob-shell"]["backing_routes"],
            ["/v1/rooms/{room_id}/blobs/{blob_id}/meta", "/api/assets", "/api/assets/{asset_id}"],
        )

        chain_rows = self.repository.list_control_plane_audit_chain(limit=10)
        blob_rows = [row for row in chain_rows if row["event_type"] == "v1_blob_meta_read"]
        self.assertGreaterEqual(len(blob_rows), 2)
        self.assertEqual(blob_rows[0]["request_id"], "req:a17-2")
        self.assertEqual(blob_rows[0]["status_code"], 400)
        self.assertEqual(blob_rows[0]["route_path"], f"/v1/rooms/{room_id}/blobs/not-a-blob-id/meta")
        self.assertEqual(blob_rows[1]["request_id"], "req:a17-1")
        self.assertEqual(blob_rows[1]["status_code"], 200)
        self.assertEqual(blob_rows[0]["prev_event_hash"], blob_rows[1]["event_hash"])

    def test_v1_surface_contains_blob_meta_object_get_and_query(self) -> None:
        v1_routes = {
            route.path: sorted(route.methods)
            for route in v1_router.routes
            if route.path.startswith("/v1")
        }
        self.assertEqual(
            v1_routes,
            {
                "/v1/capabilities": ["GET"],
                "/v1/rooms/{room_id}/blobs/{blob_id}/meta": ["GET"],
                "/v1/rooms/{room_id}/objects/get": ["POST"],
                "/v1/rooms/{room_id}/query": ["POST"],
            },
        )

    async def _perform_request(
        self,
        app,
        *,
        method: str,
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
                "method": method,
                "scheme": "http",
                "path": path,
                "raw_path": path.encode("utf-8"),
                "query_string": b"",
                "headers": header_items,
                "client": ("127.0.0.1", 50009),
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
            app_name="Klone Phase A1.7 Test",
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
