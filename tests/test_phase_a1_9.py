from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
import tempfile
import unittest
from urllib.parse import urlencode


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from klone.config import Settings  # noqa: E402
from klone.ingest import ingest_dataset  # noqa: E402
from klone.main import create_app  # noqa: E402
from klone.repository import KloneRepository  # noqa: E402
from klone.schemas import DatasetIngestRequest  # noqa: E402
from klone.v1_api import router as v1_router  # noqa: E402


class PhaseA19Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.database_path = self.root / "phase_a1_9.sqlite"
        self.repository = KloneRepository(self.database_path)
        self.repository.initialize()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_v1_changes_supports_deterministic_pagination_and_filters(self) -> None:
        first = self._ingest_dataset(
            label="A19 Change One",
            classification_level="personal",
            folder_name="a19_change_one",
            files={"one.txt": "alpha"},
        )
        second = self._ingest_dataset(
            label="A19 Change Two",
            classification_level="personal",
            folder_name="a19_change_two",
            files={"two.txt": "beta"},
        )
        self.assertEqual(first["dataset"]["room_id"], second["dataset"]["room_id"])
        room_id = first["dataset"]["room_id"]

        expected_first_page = self.repository.list_audit_events(room_id=room_id, limit=2, offset=0)
        expected_second_page = self.repository.list_audit_events(room_id=room_id, limit=2, offset=2)
        expected_completed = self.repository.list_audit_events(
            room_id=room_id,
            limit=10,
            offset=0,
            event_type="ingest_completed",
            target_type="ingest_run",
        )

        app = create_app(self._settings_for("phase_a1_9.sqlite"))
        first_page = asyncio.run(
            self._perform_request(
                app,
                method="GET",
                path=f"/v1/rooms/{room_id}/changes",
                query={"limit": 2, "offset": 0},
                headers={"x-request-id": "req:a19-changes-a", "x-trace-id": "trace:a19-changes-a"},
            )
        )
        first_page_repeat = asyncio.run(
            self._perform_request(
                app,
                method="GET",
                path=f"/v1/rooms/{room_id}/changes",
                query={"limit": 2, "offset": 0},
                headers={"x-request-id": "req:a19-changes-a-repeat", "x-trace-id": "trace:a19-changes-a-repeat"},
            )
        )
        second_page = asyncio.run(
            self._perform_request(
                app,
                method="GET",
                path=f"/v1/rooms/{room_id}/changes",
                query={"limit": 2, "offset": 2},
                headers={"x-request-id": "req:a19-changes-b", "x-trace-id": "trace:a19-changes-b"},
            )
        )
        filtered = asyncio.run(
            self._perform_request(
                app,
                method="GET",
                path=f"/v1/rooms/{room_id}/changes",
                query={"limit": 10, "offset": 0, "event_type": "ingest_completed", "target_type": "ingest_run"},
                headers={"x-request-id": "req:a19-changes-c", "x-trace-id": "trace:a19-changes-c"},
            )
        )

        self.assertEqual(first_page["status_code"], 200)
        self.assertEqual(first_page_repeat["status_code"], 200)
        self.assertEqual(second_page["status_code"], 200)
        self.assertEqual(filtered["status_code"], 200)
        self.assertEqual(first_page["json"]["backing_routes"], ["/api/audit"])
        self.assertEqual(first_page["json"]["changes"], first_page_repeat["json"]["changes"])
        self.assertEqual(
            [item["change_id"] for item in first_page["json"]["changes"]],
            [f"change:audit:{row['id']}" for row in expected_first_page],
        )
        self.assertEqual(
            [item["change_id"] for item in second_page["json"]["changes"]],
            [f"change:audit:{row['id']}" for row in expected_second_page],
        )
        self.assertEqual(
            [item["change_id"] for item in filtered["json"]["changes"]],
            [f"change:audit:{row['id']}" for row in expected_completed],
        )
        self.assertEqual(
            [item["object_id"] for item in filtered["json"]["changes"]],
            [
                f"{row['target_type']}:{row['target_id']}" if row["target_id"] is not None else f"{row['target_type']}:unknown"
                for row in expected_completed
            ],
        )
        self.assertEqual(filtered["json"]["filters"], {"event_type": "ingest_completed", "target_type": "ingest_run"})
        self.assertTrue(all(item["change_kind"] == "ingest_completed" for item in filtered["json"]["changes"]))

    def test_v1_changes_uses_summarize_permission_without_widening_object_reads(self) -> None:
        ingest_result = self._ingest_dataset(
            label="A19 Sandbox Changes",
            classification_level="restricted_bio",
            folder_name="a19_sandbox_changes",
            files={"sandbox.txt": "alpha"},
        )
        room_id = ingest_result["dataset"]["room_id"]
        self.assertEqual(room_id, "sandbox-room")

        app = create_app(self._settings_for("phase_a1_9.sqlite"))
        change_preview = asyncio.run(
            self._perform_request(
                app,
                method="GET",
                path=f"/v1/rooms/{room_id}/changes",
                query={"limit": 10, "offset": 0},
                headers={"x-request-id": "req:a19-sandbox-changes"},
            )
        )
        object_get = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path=f"/v1/rooms/{room_id}/objects/get",
                body={"object_id": f"dataset:{ingest_result['dataset']['id']}"},
                headers={"x-request-id": "req:a19-sandbox-object"},
            )
        )

        self.assertEqual(change_preview["status_code"], 200)
        self.assertEqual(object_get["status_code"], 403)
        self.assertGreaterEqual(change_preview["json"]["result_count"], 1)
        self.assertIn("outside the current room policy", object_get["json"]["detail"])

    def test_v1_changes_capabilities_and_route_surface_expose_a19_seam(self) -> None:
        ingest_result = self._ingest_dataset(
            label="A19 Capability Changes",
            classification_level="personal",
            folder_name="a19_capability_changes",
            files={"note.txt": "alpha"},
        )
        room_id = ingest_result["dataset"]["room_id"]
        app = create_app(self._settings_for("phase_a1_9.sqlite"))

        changes = asyncio.run(
            self._perform_request(
                app,
                method="GET",
                path=f"/v1/rooms/{room_id}/changes",
                query={"limit": 5, "offset": 0},
                headers={
                    "x-request-id": "req:a19-1",
                    "x-trace-id": "trace:a19-1",
                    "x-klone-principal": "owner:a19",
                    "x-klone-role": "owner",
                },
            )
        )
        capabilities = asyncio.run(self._perform_request(app, method="GET", path="/v1/capabilities"))

        self.assertEqual(changes["status_code"], 200)
        self.assertEqual(capabilities["status_code"], 200)

        capability_map = {item["id"]: item for item in capabilities["json"]["capabilities"]}
        self.assertEqual(capability_map["v1.changes.read"]["path"], "/v1/rooms/{room_id}/changes")
        self.assertEqual(capability_map["v1.changes.read"]["methods"], ["GET"])
        self.assertTrue(capability_map["v1.changes.read"]["read_only"])
        self.assertTrue(capability_map["v1.changes.read"]["room_scoped"])

        contract_map = {item["id"]: item for item in capabilities["json"]["contracts"]}
        self.assertEqual(contract_map["change-shell"]["route_readiness"], "public_read_only_changes_available")
        self.assertEqual(contract_map["change-shell"]["backing_routes"], ["/v1/rooms/{room_id}/changes", "/api/audit"])
        self.assertIn(
            "GET /v1/rooms/{room_id}/changes is the first public read-only change preview route.",
            contract_map["change-shell"]["notes"],
        )

        chain_rows = self.repository.list_control_plane_audit_chain(limit=10)
        change_rows = [row for row in chain_rows if row["event_type"] == "v1_changes_read"]
        self.assertGreaterEqual(len(change_rows), 1)
        self.assertEqual(change_rows[0]["request_id"], "req:a19-1")
        self.assertEqual(change_rows[0]["status_code"], 200)
        self.assertEqual(change_rows[0]["route_path"], f"/v1/rooms/{room_id}/changes")

        v1_routes = {
            route.path: sorted(route.methods)
            for route in v1_router.routes
            if route.path.startswith("/v1")
        }
        self.assertEqual(v1_routes["/v1/rooms/{room_id}/changes"], ["GET"])

    async def _perform_request(
        self,
        app,
        *,
        method: str,
        path: str,
        query: dict[str, object] | None = None,
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
            query_string = urlencode(query or {}, doseq=True).encode("utf-8")
            scope = {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": method,
                "scheme": "http",
                "path": path,
                "raw_path": path.encode("utf-8"),
                "query_string": query_string,
                "headers": header_items,
                "client": ("127.0.0.1", 50012),
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
            app_name="Klone Phase A1.9 Test",
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
