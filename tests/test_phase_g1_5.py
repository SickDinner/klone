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
from klone.main import create_app  # noqa: E402
from klone.repository import KloneRepository  # noqa: E402
from klone.schemas import DatasetIngestRequest  # noqa: E402


class PhaseG15Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.database_path = self.root / "phase_g1_5.sqlite"
        self.repository = KloneRepository(self.database_path)
        self.repository.initialize()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_queue_history_returns_job_events_and_linked_manifest(self) -> None:
        folder = self.root / "g15_history_completed"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "one.txt").write_text("alpha", encoding="utf-8")

        request = DatasetIngestRequest(
            label="G15 History",
            root_path=str(folder),
            collection="fixtures",
            classification_level="personal",
            description="Queue history fixture.",
        )

        app = create_app(self._settings_for("phase_g1_5.sqlite"))
        queued = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path="/api/ingest/queue",
                body=request.model_dump(mode="json"),
            )
        )
        self.assertEqual(queued["status_code"], 200)
        job_id = queued["json"]["job"]["id"]

        executed = asyncio.run(
            self._perform_request(app, method="POST", path=f"/api/ingest/queue/{job_id}/execute")
        )
        self.assertEqual(executed["status_code"], 200)
        run_id = executed["json"]["execution"]["run"]["id"]

        history = asyncio.run(
            self._perform_request(
                app,
                method="GET",
                path=f"/api/ingest/queue/{job_id}/history?room_id=restricted-room",
            )
        )

        self.assertEqual(history["status_code"], 200)
        self.assertEqual(history["json"]["room_id"], "restricted-room")
        self.assertTrue(history["json"]["read_only"])
        self.assertEqual(history["json"]["history_limit"], 16)
        self.assertEqual(history["json"]["history_event_count"], 2)
        self.assertEqual(history["json"]["job"]["id"], job_id)
        self.assertEqual(history["json"]["job"]["status"], "completed")
        self.assertEqual(history["json"]["job"]["last_run_id"], run_id)
        self.assertEqual(
            [event["event_type"] for event in history["json"]["history_events"]],
            ["ingest_queue_enqueued", "ingest_queue_completed"],
        )
        self.assertEqual(history["json"]["linked_run"]["id"], run_id)
        self.assertTrue(history["json"]["linked_run"]["has_manifest"])
        self.assertEqual(history["json"]["linked_manifest"]["run"]["id"], run_id)
        self.assertEqual(history["json"]["linked_manifest"]["run"]["files_discovered"], 1)

    def test_queue_history_is_bounded_and_deterministic(self) -> None:
        folder = self.root / "g15_history_bounded"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "one.txt").write_text("alpha", encoding="utf-8")

        request = DatasetIngestRequest(
            label="G15 Bounded",
            root_path=str(folder),
            collection="fixtures",
            classification_level="personal",
            description="Bounded queue history fixture.",
        )

        app = create_app(self._settings_for("phase_g1_5.sqlite"))
        queued = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path="/api/ingest/queue",
                body=request.model_dump(mode="json"),
            )
        )
        self.assertEqual(queued["status_code"], 200)
        job_id = queued["json"]["job"]["id"]
        self.repository.start_ingest_queue_job(job_id, room_id="restricted-room")

        reused = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path="/api/ingest/queue",
                body=request.model_dump(mode="json"),
            )
        )
        self.assertEqual(reused["status_code"], 200)
        self.assertFalse(reused["json"]["created"])
        self.assertEqual(reused["json"]["job"]["status"], "interrupted")

        executed = asyncio.run(
            self._perform_request(app, method="POST", path=f"/api/ingest/queue/{job_id}/execute")
        )
        self.assertEqual(executed["status_code"], 200)

        first = asyncio.run(
            self._perform_request(
                app,
                method="GET",
                path=f"/api/ingest/queue/{job_id}/history?room_id=restricted-room&limit=2",
            )
        )
        second = asyncio.run(
            self._perform_request(
                app,
                method="GET",
                path=f"/api/ingest/queue/{job_id}/history?room_id=restricted-room&limit=2",
            )
        )

        self.assertEqual(first["status_code"], 200)
        self.assertEqual(second["status_code"], 200)
        self.assertEqual(first["json"], second["json"])
        self.assertEqual(first["json"]["history_limit"], 2)
        self.assertEqual(first["json"]["history_event_count"], 2)
        self.assertEqual(
            [event["event_type"] for event in first["json"]["history_events"]],
            ["ingest_queue_reused", "ingest_queue_completed"],
        )

    def test_queue_history_blocks_wrong_room_and_missing_job(self) -> None:
        folder = self.root / "g15_history_room"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "one.txt").write_text("alpha", encoding="utf-8")

        request = DatasetIngestRequest(
            label="G15 Room",
            root_path=str(folder),
            collection="fixtures",
            classification_level="personal",
            description="Room-scoped queue history fixture.",
        )

        app = create_app(self._settings_for("phase_g1_5.sqlite"))
        queued = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path="/api/ingest/queue",
                body=request.model_dump(mode="json"),
            )
        )
        self.assertEqual(queued["status_code"], 200)
        job_id = queued["json"]["job"]["id"]

        wrong_room = asyncio.run(
            self._perform_request(
                app,
                method="GET",
                path=f"/api/ingest/queue/{job_id}/history?room_id=public-room",
            )
        )
        missing = asyncio.run(
            self._perform_request(
                app,
                method="GET",
                path="/api/ingest/queue/999999/history?room_id=restricted-room",
            )
        )

        self.assertEqual(wrong_room["status_code"], 404)
        self.assertIn("was not found in room public-room", wrong_room["json"]["detail"])
        self.assertEqual(missing["status_code"], 404)
        self.assertIn("was not found in room restricted-room", missing["json"]["detail"])

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

    def _settings_for(self, database_name: str) -> Settings:
        database_path = self.root / database_name
        return Settings(
            app_name="Klone Phase G1.5 Test",
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
