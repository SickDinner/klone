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
from klone.memory import MemoryService  # noqa: E402
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

    def test_v1_blob_get_returns_room_scoped_blob_metadata(self) -> None:
        ingest_result = self._ingest_dataset(
            label="Blob Get Fixture",
            classification_level="personal",
            folder_name="blob_get_fixture",
            files={"note.txt": "alpha"},
        )
        room_id = ingest_result["dataset"]["room_id"]
        services = ServiceContainer.build(self.repository)
        blob_record = services.blob.list_blob_metadata(room_id=room_id, limit=10)[0]

        app = create_app(self._settings_for("phase_a1_7.sqlite"))
        observed = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path=f"/v1/rooms/{room_id}/blobs/get",
                body={"blob_id": blob_record.blob_id},
                headers={"x-request-id": "req:a17-blob", "x-trace-id": "trace:a17-blob"},
            )
        )

        self.assertEqual(observed["status_code"], 200)
        self.assertEqual(observed["json"]["room_id"], room_id)
        self.assertEqual(observed["json"]["blob"]["blob_id"], blob_record.blob_id)
        self.assertEqual(observed["json"]["blob"]["linked_object_id"], blob_record.linked_object_id)
        self.assertEqual(observed["json"]["blob"]["asset_id"], blob_record.asset_id)
        self.assertEqual(observed["json"]["blob"]["relative_path"], "note.txt")
        self.assertEqual(observed["json"]["blob"]["metadata"]["source"], "recursive_file_scan")

    def test_v1_blob_get_blocks_wrong_room_and_invalid_blob_ids(self) -> None:
        restricted = self._ingest_dataset(
            label="Restricted Blob Fixture",
            classification_level="personal",
            folder_name="restricted_blob_fixture",
            files={"restricted.txt": "alpha"},
        )
        public = self._ingest_dataset(
            label="Public Blob Fixture",
            classification_level="public",
            folder_name="public_blob_fixture",
            files={"public.txt": "beta"},
        )
        services = ServiceContainer.build(self.repository)
        restricted_blob = services.blob.list_blob_metadata(
            room_id=restricted["dataset"]["room_id"],
            limit=10,
        )[0]

        app = create_app(self._settings_for("phase_a1_7.sqlite"))
        wrong_room = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path=f"/v1/rooms/{public['dataset']['room_id']}/blobs/get",
                body={"blob_id": restricted_blob.blob_id},
                headers={"x-request-id": "req:a17-wrong-room"},
            )
        )
        invalid = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path=f"/v1/rooms/{restricted['dataset']['room_id']}/blobs/get",
                body={"blob_id": "blob:asset:not-a-number"},
                headers={"x-request-id": "req:a17-invalid"},
            )
        )

        self.assertEqual(wrong_room["status_code"], 404)
        self.assertIn("was not found", wrong_room["json"]["detail"])
        self.assertEqual(invalid["status_code"], 400)
        self.assertIn("Blob id must end with a numeric asset id.", invalid["json"]["detail"])

    def test_v1_blob_get_writes_append_only_audit_chain_and_capabilities_expose_route(self) -> None:
        ingest_result = self._ingest_dataset(
            label="Audit Blob Fixture",
            classification_level="personal",
            folder_name="audit_blob_fixture",
            files={"note.txt": "alpha"},
        )
        room_id = ingest_result["dataset"]["room_id"]
        services = ServiceContainer.build(self.repository)
        blob_record = services.blob.list_blob_metadata(room_id=room_id, limit=10)[0]
        app = create_app(self._settings_for("phase_a1_7.sqlite"))

        first = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path=f"/v1/rooms/{room_id}/blobs/get",
                body={"blob_id": blob_record.blob_id},
                headers={
                    "x-request-id": "req:a17-1",
                    "x-trace-id": "trace:a17-1",
                    "x-klone-principal": "owner:a17",
                    "x-klone-role": "owner",
                },
            )
        )
        second = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path=f"/v1/rooms/{room_id}/blobs/get",
                body={"blob_id": "blob:asset:not-a-number"},
                headers={
                    "x-request-id": "req:a17-2",
                    "x-trace-id": "trace:a17-2",
                    "x-klone-principal": "owner:a17",
                    "x-klone-role": "owner",
                },
            )
        )
        capabilities = asyncio.run(self._perform_request(app, method="GET", path="/v1/capabilities"))

        self.assertEqual(first["status_code"], 200)
        self.assertEqual(second["status_code"], 400)
        self.assertEqual(capabilities["status_code"], 200)

        capability_map = {item["id"]: item for item in capabilities["json"]["capabilities"]}
        self.assertEqual(capability_map["v1.blobs.get"]["path"], "/v1/rooms/{room_id}/blobs/get")
        self.assertEqual(capability_map["v1.blobs.get"]["methods"], ["POST"])
        self.assertTrue(capability_map["v1.blobs.get"]["read_only"])
        self.assertTrue(capability_map["v1.blobs.get"]["room_scoped"])

        contract_map = {item["id"]: item for item in capabilities["json"]["contracts"]}
        self.assertEqual(contract_map["blob-shell"]["route_readiness"], "metadata_only_no_public_upload")
        self.assertIn("/v1/rooms/{room_id}/blobs/get", contract_map["blob-shell"]["backing_routes"])

        chain_rows = self.repository.list_control_plane_audit_chain(limit=10)
        blob_rows = [row for row in chain_rows if row["event_type"] == "v1_blob_get"]
        self.assertGreaterEqual(len(blob_rows), 2)
        self.assertEqual(blob_rows[0]["request_id"], "req:a17-2")
        self.assertEqual(blob_rows[0]["status_code"], 400)
        self.assertEqual(blob_rows[0]["route_path"], f"/v1/rooms/{room_id}/blobs/get")
        self.assertEqual(blob_rows[1]["request_id"], "req:a17-1")
        self.assertEqual(blob_rows[1]["status_code"], 200)
        self.assertEqual(blob_rows[0]["prev_event_hash"], blob_rows[1]["event_hash"])

    def test_v1_surface_contains_blob_get_route(self) -> None:
        v1_routes = {
            route.path: sorted(route.methods)
            for route in v1_router.routes
            if route.path.startswith("/v1")
        }
        self.assertEqual(v1_routes["/v1/capabilities"], ["GET"])
        self.assertEqual(v1_routes["/v1/rooms/{room_id}/blobs/get"], ["POST"])
        self.assertEqual(v1_routes["/v1/rooms/{room_id}/objects/get"], ["POST"])
        self.assertEqual(v1_routes["/v1/rooms/{room_id}/query"], ["POST"])

    async def _perform_request(
        self,
        app,
        *,
        method: str,
        path: str,
        body: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, object]:
        async with app.router.lifespan_context(app):
            events: list[dict] = []
            body_bytes = json.dumps(body).encode("utf-8") if body is not None else b""
            request_headers = dict(headers or {})
            if body is not None:
                request_headers.setdefault("content-type", "application/json")
            header_items = [
                (key.lower().encode("utf-8"), value.encode("utf-8"))
                for key, value in request_headers.items()
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

    def _seed_room(self, room_id: str) -> None:
        MemoryService(self.repository).seed_from_audit_events(
            room_id=room_id,
            audit_event_ids=[row["id"] for row in self.repository.list_audit_events(room_id=room_id, limit=20)],
        )

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
