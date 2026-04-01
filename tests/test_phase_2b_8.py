from __future__ import annotations

import asyncio
import json
from unittest.mock import patch
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


class Phase2B8Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.meta_root = self.root / "META"
        self._seed_export(self.meta_root / "facebook-export-large")

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_clone_chat_status_route_reports_local_defaults(self) -> None:
        app = create_app(self._settings_for("phase_2b_8_status.sqlite"))
        with patch.dict(
            "os.environ",
            {
                "KLONE_DIALOGUE_SOURCE": str(self.meta_root),
                "LOCALAPPDATA": str(self.root / "localappdata"),
                "OPENAI_API_KEY": "",
            },
            clear=False,
        ):
            observed = asyncio.run(self._perform_request(app, method="GET", path="/api/clone-chat/status"))

        self.assertEqual(observed["status_code"], 200)
        payload = observed["json"]
        self.assertEqual(payload["default_source_path"], str(self.meta_root))
        self.assertFalse(payload["openai_api_configured"])
        self.assertIsNone(payload["openai_key_source"])
        self.assertEqual(payload["preferred_model"], "gpt-5.4")
        self.assertEqual(payload["channel_name"], "#clone-test-room")

    def test_clone_chat_openai_configure_route_persists_local_key(self) -> None:
        app = create_app(self._settings_for("phase_2b_8_configure.sqlite"))
        local_app_data = self.root / "localappdata"
        with patch.dict(
            "os.environ",
            {"LOCALAPPDATA": str(local_app_data), "OPENAI_API_KEY": ""},
            clear=False,
        ):
            observed = asyncio.run(
                self._perform_request(
                    app,
                    method="POST",
                    path="/api/clone-chat/openai/configure",
                    body={"api_key": "sk-test-abcdefghijklmnopqrstuvwxyz", "persist": True},
                )
            )
            status = asyncio.run(self._perform_request(app, method="GET", path="/api/clone-chat/status"))

        self.assertEqual(observed["status_code"], 200)
        payload = observed["json"]
        self.assertTrue(payload["configured"])
        self.assertTrue(payload["persisted"])
        self.assertEqual(payload["key_source"], "local_file")
        self.assertTrue((local_app_data / "Klone" / "openai_api_key.txt").is_file())
        self.assertEqual(status["status_code"], 200)
        self.assertTrue(status["json"]["openai_api_configured"])
        self.assertEqual(status["json"]["openai_key_source"], "env")

    def test_clone_chat_respond_route_returns_bounded_local_reply(self) -> None:
        app = create_app(self._settings_for("phase_2b_8_reply.sqlite"))
        observed = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path="/api/clone-chat/respond",
                body={
                    "source_path": str(self.meta_root),
                    "message": "Keiden kanssa olen puhunut eniten?",
                    "mode": "bounded",
                    "history": [],
                },
            )
        )

        self.assertEqual(observed["status_code"], 200)
        payload = observed["json"]
        self.assertEqual(payload["backend_mode"], "bounded_local")
        self.assertFalse(payload["llm_call_performed"])
        self.assertIn("Alice Example", payload["reply"]["content"])
        self.assertIn("Näyttää siltä", payload["reply"]["content"])
        self.assertTrue(payload["answer"]["supported"])

    def test_clone_chat_respond_route_falls_back_when_gpt_requested_without_key(self) -> None:
        app = create_app(self._settings_for("phase_2b_8_fallback.sqlite"))
        with patch.dict(
            "os.environ",
            {"OPENAI_API_KEY": "", "LOCALAPPDATA": str(self.root / "localappdata_missing")},
            clear=False,
        ):
            observed = asyncio.run(
                self._perform_request(
                    app,
                    method="POST",
                    path="/api/clone-chat/respond",
                    body={
                        "source_path": str(self.meta_root),
                        "message": "Mitä tiedät Alice Examplesta tämän korpuksen perusteella?",
                        "mode": "gpt-5.4",
                        "history": [],
                    },
                )
            )

        self.assertEqual(observed["status_code"], 200)
        payload = observed["json"]
        self.assertEqual(payload["backend_mode"], "bounded_local")
        self.assertIn("OPENAI_API_KEY is not configured", payload["system_notes"][0])

    def test_clone_chat_respond_route_uses_openai_when_key_is_configured(self) -> None:
        app = create_app(self._settings_for("phase_2b_8_openai.sqlite"))
        local_app_data = self.root / "localappdata"
        key_dir = local_app_data / "Klone"
        key_dir.mkdir(parents=True, exist_ok=True)
        (key_dir / "openai_api_key.txt").write_text("sk-test-abcdefghijklmnopqrstuvwxyz", encoding="utf-8")
        captured_payload: dict[str, object] = {}

        def fake_openai_call(*, api_key: str, payload: dict[str, object]) -> dict[str, object]:
            captured_payload["api_key"] = api_key
            captured_payload["payload"] = payload
            return {"output_text": "Tama tuli OpenAI-polun kautta."}

        with patch.dict(
            "os.environ",
            {"LOCALAPPDATA": str(local_app_data), "OPENAI_API_KEY": ""},
            clear=False,
        ):
            with patch(
                "klone.dialogue.DialogueCorpusService._call_openai_responses_api",
                side_effect=fake_openai_call,
            ):
                observed = asyncio.run(
                    self._perform_request(
                        app,
                        method="POST",
                        path="/api/clone-chat/respond",
                        body={
                            "source_path": str(self.meta_root),
                            "message": "Keiden kanssa olen puhunut eniten?",
                            "mode": "gpt-5.4",
                            "history": [],
                        },
                    )
                )

        self.assertEqual(observed["status_code"], 200)
        payload = observed["json"]
        self.assertEqual(payload["backend_mode"], "openai_gpt_5_4")
        self.assertTrue(payload["llm_call_performed"])
        self.assertEqual(payload["reply"]["content"], "Tama tuli OpenAI-polun kautta.")
        outbound_payload = captured_payload["payload"]
        self.assertIn("You are Klone", outbound_payload["instructions"])
        self.assertIn("first-person phrasing is allowed", outbound_payload["instructions"])
        self.assertEqual(outbound_payload["input"][-1]["role"], "user")
        self.assertIsInstance(outbound_payload["input"][-1]["content"], str)

    def test_clone_chat_ui_copy_is_present(self) -> None:
        html = (PROJECT_ROOT / "src" / "klone" / "static" / "chat.html").read_text(encoding="utf-8")
        js = (PROJECT_ROOT / "src" / "klone" / "static" / "chat.js").read_text(encoding="utf-8")
        self.assertIn("#clone-test-room", html)
        self.assertIn("/api/clone-chat/respond", js)
        self.assertIn("/api/clone-chat/openai/configure", js)
        self.assertNotIn("supported:", js)

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

    def _settings_for(self, database_name: str) -> Settings:
        return Settings(
            app_name="Klone Phase 2B.8 Test",
            environment="test",
            owner_debug_mode=True,
            project_root=PROJECT_ROOT,
            data_dir=self.root / "data",
            sqlite_path=self.root / database_name,
            asset_preview_limit=12,
            audit_preview_limit=9,
        )

    def _seed_export(self, export_root: Path) -> None:
        self._write_direct_thread(
            export_root,
            section="inbox",
            slug="alice_example_1",
            title="Alice Example",
            counterpart="Alice Example",
            messages=[
                self._fb_message("Ville Olavi Peuho", 1_701_000_000_000, "Coffee tomorrow?"),
                self._fb_message("Alice Example", 1_701_000_100_000, "Yes, let's do it."),
                self._fb_message("Ville Olavi Peuho", 1_701_000_200_000, "I'll send the place."),
                self._fb_message("Alice Example", 1_701_000_300_000, "Perfect."),
            ],
        )
        self._write_direct_thread(
            export_root,
            section="inbox",
            slug="bob_example_1",
            title="Bob Example",
            counterpart="Bob Example",
            messages=[
                self._fb_message("Ville Olavi Peuho", 1_701_100_000_000, "Need the file?"),
                self._fb_message("Bob Example", 1_701_100_100_000, "Yes please."),
            ],
        )

    def _write_direct_thread(
        self,
        export_root: Path,
        *,
        section: str,
        slug: str,
        title: str,
        counterpart: str,
        messages: list[dict[str, object]],
    ) -> None:
        thread_dir = export_root / "your_facebook_activity" / "messages" / section / slug
        thread_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "title": title,
            "thread_path": f"{section}/{slug}",
            "is_still_participant": True,
            "participants": [
                {"name": counterpart},
                {"name": "Ville Olavi Peuho"},
            ],
            "messages": messages,
        }
        (thread_dir / "message_1.json").write_text(json.dumps(payload), encoding="utf-8")

    @staticmethod
    def _fb_message(sender_name: str, timestamp_ms: int, content: str) -> dict[str, object]:
        return {
            "sender_name": sender_name,
            "timestamp_ms": timestamp_ms,
            "content": content,
            "is_geoblocked_for_viewer": False,
        }


if __name__ == "__main__":
    unittest.main()
