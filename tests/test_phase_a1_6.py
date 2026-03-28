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
from klone.v1_api import router as v1_router  # noqa: E402


class PhaseA16Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.database_path = self.root / "phase_a1_6.sqlite"
        self.repository = KloneRepository(self.database_path)
        self.repository.initialize()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_v1_query_returns_memory_events_with_status_filters_and_stable_ordering(self) -> None:
        first = self._ingest_dataset(
            label="A16 Events One",
            classification_level="personal",
            folder_name="a16_events_one",
            files={"one.txt": "alpha"},
        )
        second = self._ingest_dataset(
            label="A16 Events Two",
            classification_level="personal",
            folder_name="a16_events_two",
            files={"two.txt": "beta"},
        )
        self.assertEqual(first["dataset"]["room_id"], second["dataset"]["room_id"])
        room_id = first["dataset"]["room_id"]
        self._seed_room(room_id)

        event_count_before = len(self.repository.list_memory_events(room_id=room_id, limit=100, offset=0))
        rejected_id = self.repository.list_memory_events(room_id=room_id, limit=1, offset=0)[0]["id"]
        MemoryService(self.repository).reject_event(
            room_id=room_id,
            event_id=rejected_id,
            reason="fixture_reject",
        )
        counts_before = self.repository.counts_for_room(room_id=room_id)

        app = create_app(self._settings_for("phase_a1_6.sqlite"))
        active_page_a = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path=f"/v1/rooms/{room_id}/query",
                body={
                    "query_kind": "memory_events",
                    "limit": 2,
                    "offset": 0,
                    "include_corrected": False,
                },
                headers={"x-request-id": "req:a16-events-a", "x-trace-id": "trace:a16-events-a"},
            )
        )
        active_page_b = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path=f"/v1/rooms/{room_id}/query",
                body={
                    "query_kind": "memory_events",
                    "limit": 2,
                    "offset": 0,
                    "include_corrected": False,
                },
                headers={"x-request-id": "req:a16-events-b", "x-trace-id": "trace:a16-events-b"},
            )
        )
        rejected_page = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path=f"/v1/rooms/{room_id}/query",
                body={
                    "query_kind": "memory_events",
                    "limit": 5,
                    "offset": 0,
                    "status": "rejected",
                },
                headers={"x-request-id": "req:a16-events-c", "x-trace-id": "trace:a16-events-c"},
            )
        )

        self.assertEqual(active_page_a["status_code"], 200)
        self.assertEqual(active_page_b["status_code"], 200)
        self.assertEqual(rejected_page["status_code"], 200)
        self.assertEqual(active_page_a["json"]["backing_routes"], ["/api/memory/events"])
        self.assertEqual(active_page_a["json"]["query_id"], "query:req:a16-events-a")
        self.assertEqual(active_page_a["json"]["results"], active_page_b["json"]["results"])
        self.assertTrue(all(item["room_id"] == room_id for item in active_page_a["json"]["results"]))
        self.assertTrue(all(item["status"] == "active" for item in active_page_a["json"]["results"]))
        self.assertTrue(all("provenance_summary" in item for item in active_page_a["json"]["results"]))
        self.assertEqual(rejected_page["json"]["filters"]["status"], "rejected")
        self.assertEqual(rejected_page["json"]["results"][0]["id"], rejected_id)
        self.assertEqual(rejected_page["json"]["results"][0]["status"], "rejected")

        counts_after = self.repository.counts_for_room(room_id=room_id)
        self.assertEqual(counts_before["dataset_count"], counts_after["dataset_count"])
        self.assertEqual(counts_before["asset_count"], counts_after["asset_count"])
        self.assertEqual(
            event_count_before,
            len(self.repository.list_memory_events(room_id=room_id, limit=100, offset=0)),
        )

    def test_v1_query_returns_memory_episodes_with_stable_pagination(self) -> None:
        first = self._ingest_dataset(
            label="A16 Episodes One",
            classification_level="personal",
            folder_name="a16_episodes_one",
            files={"one.txt": "alpha"},
        )
        second = self._ingest_dataset(
            label="A16 Episodes Two",
            classification_level="personal",
            folder_name="a16_episodes_two",
            files={"two.txt": "beta"},
        )
        self.assertEqual(first["dataset"]["room_id"], second["dataset"]["room_id"])
        room_id = first["dataset"]["room_id"]
        self._seed_room(room_id)
        memory_service = MemoryService(self.repository)
        expected_first_page = memory_service.query_episodes(
            room_id=room_id,
            limit=1,
            offset=0,
            include_corrected=True,
        )
        expected_second_page = memory_service.query_episodes(
            room_id=room_id,
            limit=1,
            offset=1,
            include_corrected=True,
        )

        episode_rows = self.repository.list_memory_episodes(room_id=room_id, limit=10, offset=0)
        rejected_episode_id = episode_rows[-1]["id"]
        MemoryService(self.repository).reject_episode(
            room_id=room_id,
            episode_id=rejected_episode_id,
            reason="fixture_reject_episode",
        )

        app = create_app(self._settings_for("phase_a1_6.sqlite"))
        first_page = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path=f"/v1/rooms/{room_id}/query",
                body={
                    "query_kind": "memory_episodes",
                    "limit": 1,
                    "offset": 0,
                    "include_corrected": True,
                },
                headers={"x-request-id": "req:a16-episodes-a"},
            )
        )
        first_page_repeat = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path=f"/v1/rooms/{room_id}/query",
                body={
                    "query_kind": "memory_episodes",
                    "limit": 1,
                    "offset": 0,
                    "include_corrected": True,
                },
                headers={"x-request-id": "req:a16-episodes-a-repeat"},
            )
        )
        second_page = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path=f"/v1/rooms/{room_id}/query",
                body={
                    "query_kind": "memory_episodes",
                    "limit": 1,
                    "offset": 1,
                    "include_corrected": True,
                },
                headers={"x-request-id": "req:a16-episodes-b"},
            )
        )
        rejected_page = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path=f"/v1/rooms/{room_id}/query",
                body={
                    "query_kind": "memory_episodes",
                    "limit": 5,
                    "offset": 0,
                    "status": "rejected",
                },
                headers={"x-request-id": "req:a16-episodes-c"},
            )
        )

        self.assertEqual(first_page["status_code"], 200)
        self.assertEqual(first_page_repeat["status_code"], 200)
        self.assertEqual(second_page["status_code"], 200)
        self.assertEqual(rejected_page["status_code"], 200)
        self.assertEqual(first_page["json"]["backing_routes"], ["/api/memory/episodes"])
        self.assertEqual(first_page["json"]["results"], first_page_repeat["json"]["results"])
        self.assertNotEqual(first_page["json"]["results"][0]["id"], second_page["json"]["results"][0]["id"])
        self.assertEqual(first_page["json"]["filters"], {"include_corrected": True})
        self.assertEqual(first_page["json"]["results"][0]["id"], expected_first_page[0]["id"])
        self.assertEqual(first_page["json"]["results"][0]["title"], expected_first_page[0]["title"])
        self.assertEqual(second_page["json"]["results"][0]["id"], expected_second_page[0]["id"])
        self.assertEqual(second_page["json"]["results"][0]["title"], expected_second_page[0]["title"])
        self.assertTrue(first_page["json"]["results"][0]["title"].startswith("system_ingest_run:"))
        self.assertTrue(second_page["json"]["results"][0]["title"].startswith("system_ingest_run:"))
        self.assertEqual(rejected_page["json"]["results"][0]["id"], rejected_episode_id)
        self.assertEqual(rejected_page["json"]["results"][0]["status"], "rejected")

    def test_v1_query_preserves_room_isolation_and_blocks_mismatched_filter_shape(self) -> None:
        restricted = self._ingest_dataset(
            label="A16 Restricted",
            classification_level="personal",
            folder_name="a16_restricted",
            files={"restricted.txt": "alpha"},
        )
        public = self._ingest_dataset(
            label="A16 Public",
            classification_level="public",
            folder_name="a16_public",
            files={"public.txt": "beta"},
        )
        self._seed_room(restricted["dataset"]["room_id"])
        self._seed_room(public["dataset"]["room_id"])

        app = create_app(self._settings_for("phase_a1_6.sqlite"))
        public_query = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path=f"/v1/rooms/{public['dataset']['room_id']}/query",
                body={"query_kind": "memory_events", "limit": 20, "offset": 0},
                headers={"x-request-id": "req:a16-room"},
            )
        )
        invalid_query = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path=f"/v1/rooms/{restricted['dataset']['room_id']}/query",
                body={"query_kind": "memory_episodes", "event_type": "ingest_started"},
                headers={"x-request-id": "req:a16-invalid"},
            )
        )

        self.assertEqual(public_query["status_code"], 200)
        self.assertTrue(
            all(item["room_id"] == public["dataset"]["room_id"] for item in public_query["json"]["results"])
        )
        self.assertFalse(
            any(item["room_id"] == restricted["dataset"]["room_id"] for item in public_query["json"]["results"])
        )
        self.assertEqual(invalid_query["status_code"], 400)
        self.assertIn("event_type is only supported for memory_events queries", invalid_query["json"]["detail"])

    def test_v1_query_writes_audit_chain_and_capabilities_expose_query_shell(self) -> None:
        ingest_result = self._ingest_dataset(
            label="A16 Audit",
            classification_level="personal",
            folder_name="a16_audit",
            files={"note.txt": "alpha"},
        )
        room_id = ingest_result["dataset"]["room_id"]
        self._seed_room(room_id)
        app = create_app(self._settings_for("phase_a1_6.sqlite"))

        query_response = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path=f"/v1/rooms/{room_id}/query",
                body={"query_kind": "memory_events"},
                headers={
                    "x-request-id": "req:a16-1",
                    "x-trace-id": "trace:a16-1",
                    "x-klone-principal": "owner:a16",
                    "x-klone-role": "owner",
                },
            )
        )
        blocked_response = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path=f"/v1/rooms/{room_id}/query",
                body={"query_kind": "memory_episodes", "event_type": "ingest_started"},
                headers={
                    "x-request-id": "req:a16-2",
                    "x-trace-id": "trace:a16-2",
                    "x-klone-principal": "owner:a16",
                    "x-klone-role": "owner",
                },
            )
        )
        capabilities = asyncio.run(self._perform_request(app, method="GET", path="/v1/capabilities"))

        self.assertEqual(query_response["status_code"], 200)
        self.assertEqual(blocked_response["status_code"], 400)
        self.assertEqual(capabilities["status_code"], 200)

        capability_map = {item["id"]: item for item in capabilities["json"]["capabilities"]}
        self.assertEqual(capability_map["v1.query.read"]["path"], "/v1/rooms/{room_id}/query")
        self.assertEqual(capability_map["v1.query.read"]["methods"], ["POST"])
        self.assertTrue(capability_map["v1.query.read"]["read_only"])
        self.assertTrue(capability_map["v1.query.read"]["room_scoped"])

        contract_map = {item["id"]: item for item in capabilities["json"]["contracts"]}
        self.assertEqual(contract_map["query-shell"]["route_readiness"], "public_read_only_query_available")
        self.assertEqual(
            contract_map["query-shell"]["backing_routes"],
            ["/v1/rooms/{room_id}/query", "/api/memory/events", "/api/memory/episodes"],
        )

        chain_rows = self.repository.list_control_plane_audit_chain(limit=10)
        query_rows = [row for row in chain_rows if row["event_type"] == "v1_query_read"]
        self.assertGreaterEqual(len(query_rows), 2)
        self.assertEqual(query_rows[0]["request_id"], "req:a16-2")
        self.assertEqual(query_rows[0]["status_code"], 400)
        self.assertEqual(query_rows[0]["route_path"], f"/v1/rooms/{room_id}/query")
        self.assertEqual(query_rows[1]["request_id"], "req:a16-1")
        self.assertEqual(query_rows[1]["status_code"], 200)
        self.assertEqual(query_rows[0]["prev_event_hash"], query_rows[1]["event_hash"])

    def test_v1_surface_contains_blob_get_object_get_and_query(self) -> None:
        v1_routes = {
            route.path: sorted(route.methods)
            for route in v1_router.routes
            if route.path.startswith("/v1")
        }
        self.assertEqual(v1_routes["/v1/capabilities"], ["GET"])
        self.assertEqual(v1_routes["/v1/rooms/{room_id}/blobs/{blob_id}/meta"], ["GET"])
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
                "client": ("127.0.0.1", 50008),
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
        audit_rows = self.repository.list_audit_events(room_id=room_id, limit=20)
        MemoryService(self.repository).seed_from_audit_events(
            room_id=room_id,
            audit_event_ids=[row["id"] for row in audit_rows],
        )

    def _settings_for(self, database_name: str) -> Settings:
        database_path = self.root / database_name
        return Settings(
            app_name="Klone Phase A1.6 Test",
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
