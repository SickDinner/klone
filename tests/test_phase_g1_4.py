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


class PhaseG14Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.database_path = self.root / "phase_g1_4.sqlite"
        self.repository = KloneRepository(self.database_path)
        self.repository.initialize()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_startup_recovery_marks_running_job_interrupted(self) -> None:
        folder = self.root / "g14_interrupted"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "one.txt").write_text("alpha", encoding="utf-8")

        request = DatasetIngestRequest(
            label="G14 Interrupted",
            root_path=str(folder),
            collection="fixtures",
            classification_level="personal",
            description="Interrupted queue recovery fixture.",
        )

        app = create_app(self._settings_for("phase_g1_4.sqlite"))
        queued = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path="/api/ingest/queue",
                body=request.model_dump(mode="json"),
            )
        )
        job_id = queued["json"]["job"]["id"]
        self.repository.start_ingest_queue_job(job_id, room_id="restricted-room")

        queue_list = asyncio.run(
            self._perform_request(app, method="GET", path="/api/ingest/queue?room_id=restricted-room")
        )
        ingest_status = asyncio.run(
            self._perform_request(app, method="GET", path="/api/ingest/status?room_id=restricted-room")
        )
        audit = asyncio.run(
            self._perform_request(app, method="GET", path="/api/audit?room_id=restricted-room")
        )

        self.assertEqual(queue_list["status_code"], 200)
        self.assertEqual(ingest_status["status_code"], 200)
        self.assertEqual(audit["status_code"], 200)
        self.assertEqual(queue_list["json"][0]["status"], "interrupted")
        self.assertTrue(queue_list["json"][0]["can_execute"])
        self.assertTrue(queue_list["json"][0]["can_cancel"])
        self.assertEqual(queue_list["json"][0]["last_error"], "interrupted_before_completion")
        self.assertEqual(ingest_status["json"]["queue_depth"], 1)
        self.assertEqual(ingest_status["json"]["latest_queue_job"]["status"], "interrupted")
        self.assertTrue(
            any(event["event_type"] == "ingest_queue_interrupted" for event in audit["json"])
        )

    def test_interrupted_job_can_resume_through_existing_execute_route(self) -> None:
        folder = self.root / "g14_resume"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "resume.txt").write_text("beta", encoding="utf-8")

        request = DatasetIngestRequest(
            label="G14 Resume",
            root_path=str(folder),
            collection="fixtures",
            classification_level="personal",
            description="Resume interrupted queue job.",
        )

        app = create_app(self._settings_for("phase_g1_4.sqlite"))
        queued = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path="/api/ingest/queue",
                body=request.model_dump(mode="json"),
            )
        )
        job_id = queued["json"]["job"]["id"]
        self.repository.start_ingest_queue_job(job_id, room_id="restricted-room")

        resumed = asyncio.run(
            self._perform_request(app, method="POST", path=f"/api/ingest/queue/{job_id}/execute")
        )
        manifest = asyncio.run(
            self._perform_request(
                app,
                method="GET",
                path=f"/api/ingest/runs/{resumed['json']['execution']['run']['id']}/manifest",
            )
        )
        ingest_status = asyncio.run(
            self._perform_request(app, method="GET", path="/api/ingest/status?room_id=restricted-room")
        )

        self.assertEqual(resumed["status_code"], 200)
        self.assertEqual(resumed["json"]["job"]["status"], "completed")
        self.assertEqual(resumed["json"]["job"]["attempt_count"], 2)
        self.assertEqual(resumed["json"]["execution"]["run"]["trigger_source"], "queue_job")
        self.assertEqual(manifest["status_code"], 200)
        self.assertEqual(ingest_status["json"]["queue_depth"], 0)
        self.assertEqual(ingest_status["json"]["recent_queue_jobs"][0]["status"], "completed")

    def test_queue_stage_reuses_interrupted_job_for_same_root(self) -> None:
        folder = self.root / "g14_reuse"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "reuse.txt").write_text("gamma", encoding="utf-8")

        request = DatasetIngestRequest(
            label="G14 Reuse",
            root_path=str(folder),
            collection="fixtures",
            classification_level="personal",
            description="Reuse interrupted queue job.",
        )

        app = create_app(self._settings_for("phase_g1_4.sqlite"))
        queued = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path="/api/ingest/queue",
                body=request.model_dump(mode="json"),
            )
        )
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
        self.assertEqual(reused["json"]["job"]["id"], job_id)
        self.assertEqual(reused["json"]["job"]["status"], "interrupted")
        self.assertTrue(reused["json"]["job"]["can_execute"])
        self.assertTrue(reused["json"]["job"]["can_cancel"])

    def test_interrupted_resume_copy_is_present_in_ui(self) -> None:
        js = (PROJECT_ROOT / "src" / "klone" / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn('job.status === "interrupted" ? "Resume" : "Execute"', js)
        self.assertIn("interrupted-run recovery", js)

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
            app_name="Klone Phase G1.4 Test",
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
