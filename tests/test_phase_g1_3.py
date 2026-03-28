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


class PhaseG13Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.database_path = self.root / "phase_g1_3.sqlite"
        self.repository = KloneRepository(self.database_path)
        self.repository.initialize()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_ingest_queue_stage_execute_and_manifest_visibility(self) -> None:
        folder = self.root / "g13_queue"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "one.txt").write_text("alpha", encoding="utf-8")
        (folder / "two.txt").write_text("beta", encoding="utf-8")

        request = DatasetIngestRequest(
            label="G13 Queue",
            root_path=str(folder),
            collection="fixtures",
            classification_level="personal",
            description="Queue execution fixture.",
        )

        app = create_app(self._settings_for("phase_g1_3.sqlite"))
        queued = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path="/api/ingest/queue",
                body=request.model_dump(mode="json"),
            )
        )
        self.assertEqual(queued["status_code"], 200)
        self.assertTrue(queued["json"]["created"])
        self.assertEqual(queued["json"]["job"]["status"], "queued")
        self.assertTrue(queued["json"]["job"]["can_execute"])
        self.assertTrue(queued["json"]["job"]["can_cancel"])

        job_id = queued["json"]["job"]["id"]

        ingest_status = asyncio.run(
            self._perform_request(app, method="GET", path="/api/ingest/status?room_id=restricted-room")
        )
        queue_list = asyncio.run(
            self._perform_request(app, method="GET", path="/api/ingest/queue?room_id=restricted-room")
        )
        self.assertEqual(ingest_status["status_code"], 200)
        self.assertEqual(queue_list["status_code"], 200)
        self.assertEqual(ingest_status["json"]["queue_depth"], 1)
        self.assertEqual(ingest_status["json"]["latest_queue_job"]["id"], job_id)
        self.assertEqual(queue_list["json"][0]["id"], job_id)

        executed = asyncio.run(
            self._perform_request(app, method="POST", path=f"/api/ingest/queue/{job_id}/execute")
        )
        self.assertEqual(executed["status_code"], 200)
        self.assertEqual(executed["json"]["job"]["status"], "completed")
        self.assertIsNone(executed["json"]["error"])
        self.assertEqual(executed["json"]["execution"]["run"]["status"], "completed")
        self.assertGreater(executed["json"]["execution"]["run"]["id"], 0)

        run_id = executed["json"]["execution"]["run"]["id"]

        manifest = asyncio.run(
            self._perform_request(app, method="GET", path=f"/api/ingest/runs/{run_id}/manifest")
        )
        ingest_status_after = asyncio.run(
            self._perform_request(app, method="GET", path="/api/ingest/status?room_id=restricted-room")
        )
        self.assertEqual(manifest["status_code"], 200)
        self.assertEqual(ingest_status_after["status_code"], 200)
        self.assertEqual(ingest_status_after["json"]["queue_depth"], 0)
        self.assertEqual(ingest_status_after["json"]["recent_queue_jobs"][0]["status"], "completed")
        self.assertEqual(manifest["json"]["run"]["id"], run_id)
        self.assertEqual(manifest["json"]["run"]["files_discovered"], 2)
        self.assertEqual(manifest["json"]["run"]["new_assets"], 2)

    def test_ingest_queue_reuses_active_job_and_supports_cancel(self) -> None:
        folder = self.root / "g13_reuse"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "item.txt").write_text("alpha", encoding="utf-8")

        request = DatasetIngestRequest(
            label="G13 Reuse",
            root_path=str(folder),
            collection="fixtures",
            classification_level="personal",
            description="Queue reuse fixture.",
        )

        app = create_app(self._settings_for("phase_g1_3.sqlite"))
        first = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path="/api/ingest/queue",
                body=request.model_dump(mode="json"),
            )
        )
        second = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path="/api/ingest/queue",
                body=request.model_dump(mode="json"),
            )
        )
        self.assertEqual(first["status_code"], 200)
        self.assertEqual(second["status_code"], 200)
        self.assertTrue(first["json"]["created"])
        self.assertFalse(second["json"]["created"])
        self.assertEqual(first["json"]["job"]["id"], second["json"]["job"]["id"])

        job_id = first["json"]["job"]["id"]
        cancelled = asyncio.run(
            self._perform_request(app, method="POST", path=f"/api/ingest/queue/{job_id}/cancel")
        )
        self.assertEqual(cancelled["status_code"], 200)
        self.assertEqual(cancelled["json"]["status"], "cancelled")
        self.assertFalse(cancelled["json"]["can_execute"])
        self.assertFalse(cancelled["json"]["can_cancel"])

        execute_cancelled = asyncio.run(
            self._perform_request(app, method="POST", path=f"/api/ingest/queue/{job_id}/execute")
        )
        ingest_status = asyncio.run(
            self._perform_request(app, method="GET", path="/api/ingest/status?room_id=restricted-room")
        )
        self.assertEqual(execute_cancelled["status_code"], 409)
        self.assertIn("cannot start from status cancelled", execute_cancelled["json"]["detail"])
        self.assertEqual(ingest_status["json"]["queue_depth"], 0)

    def test_ingest_queue_ui_text_is_present(self) -> None:
        html = (PROJECT_ROOT / "src" / "klone" / "static" / "index.html").read_text(encoding="utf-8")
        js = (PROJECT_ROOT / "src" / "klone" / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("Queue Dataset", html)
        self.assertIn("Ingest Queue and Runs", html)
        self.assertIn("renderIngestQueueJobs", js)
        self.assertIn("/api/ingest/queue", js)
        self.assertIn("data-queue-action", js)

    def test_startup_recovery_marks_running_job_interrupted_without_auto_execution(self) -> None:
        folder = self.root / "g13_startup"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "item.txt").write_text("alpha", encoding="utf-8")

        request = DatasetIngestRequest(
            label="G13 Startup",
            root_path=str(folder),
            collection="fixtures",
            classification_level="personal",
            description="Startup recovery boundary fixture.",
        )

        staged_job, _ = self.repository.enqueue_ingest_queue_job(
            label=request.label,
            normalized_root_path=str(folder),
            room_id="restricted-room",
            classification_level=request.classification_level,
            collection=request.collection,
            description=request.description,
            request_payload=request.model_dump(mode="json"),
        )
        running_job = self.repository.start_ingest_queue_job(staged_job["id"], room_id="restricted-room")
        self.assertEqual(running_job["status"], "running")

        app = create_app(self._settings_for("phase_g1_3.sqlite"))
        asyncio.run(self._enter_and_leave_lifespan(app))

        observed_job = self.repository.get_ingest_queue_job(running_job["id"], room_id="restricted-room")
        self.assertIsNotNone(observed_job)
        self.assertEqual(observed_job["status"], "interrupted")
        self.assertEqual(observed_job["last_error"], "interrupted_before_completion")
        ingest_runs = self.repository.list_ingest_runs(room_id="restricted-room", limit=10)
        self.assertEqual(ingest_runs, [])
        audit_rows = self.repository.list_audit_events(room_id="restricted-room", limit=20)
        self.assertIn("ingest_queue_interrupted", {row["event_type"] for row in audit_rows})

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
            payload = json.loads(response_body.decode("utf-8"))
            return {
                "status_code": response_start["status"],
                "json": payload,
            }

    def _settings_for(self, database_name: str) -> Settings:
        database_path = self.root / database_name
        return Settings(
            app_name="Klone Phase G1.3 Test",
            environment="test",
            owner_debug_mode=True,
            project_root=PROJECT_ROOT,
            data_dir=self.root / "data",
            sqlite_path=database_path,
            asset_preview_limit=12,
            audit_preview_limit=9,
        )

    async def _enter_and_leave_lifespan(self, app) -> None:
        async with app.router.lifespan_context(app):
            return None


if __name__ == "__main__":
    unittest.main()
