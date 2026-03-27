from __future__ import annotations

import asyncio
import sys
from pathlib import Path
import tempfile
import unittest

from starlette.requests import Request


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from klone.api import health, status  # noqa: E402
from klone.config import Settings  # noqa: E402
from klone.contracts import BOOTSTRAP_TASK_ID, BOOTSTRAP_VERSION, SCHEMA_VERSION  # noqa: E402
from klone.main import create_app  # noqa: E402


class BedrockB002Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_startup_records_bootstrap_run_and_surfaces_it(self) -> None:
        app = create_app(self._settings_for("bedrock_jobs.sqlite"))
        observed = asyncio.run(self._collect_runtime_payloads(app))

        latest_internal_run = observed["status"]["latest_internal_run"]
        recent_internal_runs = observed["status"]["recent_internal_runs"]

        self.assertIsNotNone(latest_internal_run)
        self.assertEqual(len(recent_internal_runs), 1)
        self.assertEqual(latest_internal_run["id"], recent_internal_runs[0]["id"])
        self.assertEqual(latest_internal_run["task_id"], BOOTSTRAP_TASK_ID)
        self.assertEqual(latest_internal_run["run_kind"], "bootstrap")
        self.assertEqual(latest_internal_run["status"], "completed")
        self.assertEqual(latest_internal_run["trigger"], "startup")
        self.assertIsNone(latest_internal_run["room_id"])
        self.assertTrue(latest_internal_run["id"].startswith("run:bootstrap:system:"))
        self.assertEqual(
            latest_internal_run["trace_id"],
            latest_internal_run["id"].replace("run:", "trace:", 1),
        )
        self.assertEqual(latest_internal_run["metadata"]["bootstrap_version"], BOOTSTRAP_VERSION)
        self.assertEqual(latest_internal_run["metadata"]["schema_version"], SCHEMA_VERSION)
        self.assertEqual(latest_internal_run["metadata"]["bootstrap_mode"], "fresh_db")
        self.assertEqual(latest_internal_run["metadata"]["missing_tables"], [])
        self.assertTrue(latest_internal_run["metadata"]["correction_schema_ready"])
        self.assertEqual(observed["health"]["latest_internal_run_id"], latest_internal_run["id"])
        self.assertEqual(observed["health"]["latest_internal_run_status"], "completed")
        self.assertEqual(observed["health"]["latest_internal_trace_id"], latest_internal_run["trace_id"])

    def test_repeated_startup_adds_ordered_run_history(self) -> None:
        db_name = "bedrock_jobs_history.sqlite"
        first_payload = asyncio.run(
            self._collect_runtime_payloads(create_app(self._settings_for(db_name)))
        )["status"]
        second_payload = asyncio.run(
            self._collect_runtime_payloads(create_app(self._settings_for(db_name)))
        )["status"]

        self.assertEqual(first_payload["bootstrap"]["bootstrap_mode"], "fresh_db")
        self.assertEqual(second_payload["bootstrap"]["bootstrap_mode"], "existing_db")
        self.assertGreaterEqual(len(second_payload["recent_internal_runs"]), 2)

        newest_run = second_payload["recent_internal_runs"][0]
        older_run = second_payload["recent_internal_runs"][1]

        self.assertEqual(newest_run["task_id"], BOOTSTRAP_TASK_ID)
        self.assertEqual(older_run["task_id"], BOOTSTRAP_TASK_ID)
        self.assertEqual(newest_run["run_kind"], "bootstrap")
        self.assertEqual(older_run["run_kind"], "bootstrap")
        self.assertNotEqual(newest_run["id"], older_run["id"])
        self.assertGreaterEqual(newest_run["started_at"], older_run["started_at"])
        self.assertEqual(second_payload["latest_internal_run"]["id"], newest_run["id"])
        self.assertEqual(newest_run["metadata"]["bootstrap_mode"], "existing_db")
        self.assertEqual(older_run["metadata"]["bootstrap_mode"], "fresh_db")

    async def _collect_runtime_payloads(self, app) -> dict[str, object]:
        async with app.router.lifespan_context(app):
            repository = app.state.repository
            status_request = self._request_for(app, path="/api/status")
            health_request = self._request_for(app, path="/api/health")
            return {
                "health": health(health_request, repository=repository),
                "status": status(status_request, repository=repository).model_dump(mode="json"),
            }

    def _request_for(self, app, *, path: str) -> Request:
        scope = {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode("utf-8"),
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 50000),
            "server": ("testserver", 80),
            "app": app,
        }
        return Request(scope)

    def _settings_for(self, database_name: str) -> Settings:
        database_path = self.root / database_name
        return Settings(
            app_name="Klone Bedrock Jobs Test",
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
