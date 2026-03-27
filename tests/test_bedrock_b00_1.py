from __future__ import annotations

import asyncio
import sys
from pathlib import Path
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from starlette.requests import Request  # noqa: E402

from klone.api import blueprint, health, status  # noqa: E402
from klone.blueprint import SYSTEM_BLUEPRINT  # noqa: E402
from klone.config import Settings  # noqa: E402
from klone.contracts import APP_VERSION, BOOTSTRAP_VERSION, MODULE_REGISTRY_VERSION, SCHEMA_VERSION  # noqa: E402
from klone.main import create_app  # noqa: E402


class BedrockB001Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_status_exposes_runtime_bootstrap_and_module_registry(self) -> None:
        app = create_app(self._settings_for("bedrock_status.sqlite"))
        observed = asyncio.run(self._collect_runtime_payloads(app))
        health_payload = observed["health"]
        status_payload = observed["status"]
        blueprint_payload = observed["blueprint"]
        state_settings = observed["state_settings"]
        bootstrap_report = observed["bootstrap_report"]

        self.assertEqual(health_payload["app"], "Klone Bedrock Test")
        self.assertEqual(health_payload["app_version"], APP_VERSION)
        self.assertEqual(health_payload["bootstrap_version"], BOOTSTRAP_VERSION)
        self.assertEqual(health_payload["schema_version"], SCHEMA_VERSION)
        self.assertEqual(health_payload["bootstrap_mode"], "fresh_db")
        self.assertTrue(health_payload["correction_schema_ready"])

        self.assertEqual(status_payload["app_name"], "Klone Bedrock Test")
        self.assertEqual(status_payload["app_version"], APP_VERSION)
        self.assertEqual(status_payload["bootstrap_version"], BOOTSTRAP_VERSION)
        self.assertEqual(status_payload["schema_version"], SCHEMA_VERSION)
        self.assertEqual(status_payload["module_registry_version"], MODULE_REGISTRY_VERSION)
        self.assertEqual(status_payload["runtime_config"]["environment"], "test")
        self.assertEqual(status_payload["runtime_config"]["database_path"], str(self.root / "bedrock_status.sqlite"))
        self.assertEqual(status_payload["runtime_config"]["asset_preview_limit"], 12)
        self.assertEqual(status_payload["runtime_config"]["audit_preview_limit"], 9)
        self.assertEqual(status_payload["bootstrap"]["bootstrap_mode"], "fresh_db")
        self.assertEqual(status_payload["bootstrap"]["missing_tables"], [])
        self.assertTrue(status_payload["bootstrap"]["correction_schema_ready"])
        self.assertEqual(
            [module["id"] for module in status_payload["module_registry"]],
            [module.id for module in SYSTEM_BLUEPRINT.modules],
        )
        self.assertEqual(
            [module["capability_count"] for module in status_payload["module_registry"]],
            [len(module.key_inputs) + len(module.outputs) for module in SYSTEM_BLUEPRINT.modules],
        )
        self.assertEqual(
            [module["id"] for module in blueprint_payload["modules"]],
            [module.id for module in SYSTEM_BLUEPRINT.modules],
        )

        self.assertEqual(state_settings.app_name, "Klone Bedrock Test")
        self.assertEqual(bootstrap_report["schema_version"], SCHEMA_VERSION)
        self.assertEqual(bootstrap_report["missing_tables"], [])

    def test_bootstrap_visibility_is_deterministic_for_fresh_and_existing_db(self) -> None:
        db_name = "bedrock_existing.sqlite"
        first_app = create_app(self._settings_for(db_name))
        first_payload = asyncio.run(self._collect_runtime_payloads(first_app))["status"]

        second_app = create_app(self._settings_for(db_name))
        second_payload = asyncio.run(self._collect_runtime_payloads(second_app))["status"]

        self.assertEqual(first_payload["bootstrap"]["bootstrap_mode"], "fresh_db")
        self.assertEqual(second_payload["bootstrap"]["bootstrap_mode"], "existing_db")
        self.assertEqual(first_payload["bootstrap"]["schema_version"], second_payload["bootstrap"]["schema_version"])
        self.assertEqual(first_payload["bootstrap"]["schema_user_version"], second_payload["bootstrap"]["schema_user_version"])
        self.assertEqual(first_payload["bootstrap"]["expected_tables"], second_payload["bootstrap"]["expected_tables"])
        self.assertEqual(first_payload["bootstrap"]["missing_tables"], [])
        self.assertEqual(second_payload["bootstrap"]["missing_tables"], [])
        self.assertEqual(first_payload["module_registry"], second_payload["module_registry"])

    async def _collect_runtime_payloads(self, app) -> dict[str, object]:
        async with app.router.lifespan_context(app):
            request = self._request_for(app, path="/api/status")
            repository = app.state.repository
            return {
                "health": health(self._request_for(app, path="/api/health"), repository=repository),
                "status": status(request, repository=repository).model_dump(mode="json"),
                "blueprint": blueprint(),
                "state_settings": app.state.settings,
                "bootstrap_report": dict(app.state.bootstrap_report),
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
            app_name="Klone Bedrock Test",
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
