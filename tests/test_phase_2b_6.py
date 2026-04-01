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


class Phase2B6Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_dialogue_corpus_route_selects_richest_facebook_export_root(self) -> None:
        meta_root = self.root / "META"
        export_small = meta_root / "facebook-export-small"
        export_large = meta_root / "facebook-export-large"
        self._write_direct_thread(
            export_small,
            section="inbox",
            slug="oldfriend_1",
            title="Old Friend",
            counterpart="Old Friend",
            messages=[
                self._fb_message("Ville Olavi Peuho", 1_700_000_000_000, "Quick ping."),
                self._fb_message("Old Friend", 1_700_000_100_000, "Ping back."),
            ],
        )
        self._write_direct_thread(
            export_large,
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
        self._write_group_thread(
            export_large,
            section="inbox",
            slug="project_circle_1",
            title="Project Circle",
            participants=["Ville Olavi Peuho", "Bob Example", "Cara Example"],
            messages=[
                self._fb_message("Bob Example", 1_701_100_000_000, "Can we meet this week?"),
                self._fb_message("Ville Olavi Peuho", 1_701_100_100_000, "Yes, I can do Thursday."),
                self._fb_message("Cara Example", 1_701_100_200_000, "Thursday works for me too."),
            ],
        )
        self._write_direct_thread(
            export_large,
            section="message_requests",
            slug="dana_request_1",
            title="Dana Request",
            counterpart="Dana Request",
            messages=[
                self._fb_message("Dana Request", 1_701_200_000_000, "Hi, are you the right Ville?"),
                self._fb_message(
                    "Ville Olavi Peuho",
                    1_701_200_100_000,
                    "Yes, that's me.",
                    photos=[{"uri": "photos/one.jpg"}],
                ),
            ],
        )

        app = create_app(self._settings_for("phase_2b_6.sqlite"))
        observed = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path="/api/dialogue-corpus/analyze",
                body={"source_path": str(meta_root)},
            )
        )

        self.assertEqual(observed["status_code"], 200)
        payload = observed["json"]
        self.assertEqual(payload["analysis_version"], "2b.6.read_only_dialogue_corpus_shell")
        self.assertEqual(payload["source_kind"], "facebook_messenger_export")
        self.assertEqual(payload["selected_source_path"], str(export_large))
        self.assertEqual(payload["owner_name"], "Ville Olavi Peuho")
        self.assertEqual(payload["thread_count"], 3)
        self.assertEqual(payload["direct_thread_count"], 2)
        self.assertEqual(payload["group_thread_count"], 1)
        self.assertEqual(payload["counterpart_count"], 4)
        self.assertEqual(payload["message_count"], 9)
        self.assertEqual(payload["sent_message_count"], 4)
        self.assertEqual(payload["received_message_count"], 5)
        self.assertEqual(payload["attachment_message_count"], 1)
        self.assertEqual(payload["recommended_room_id"], "intimate")
        self.assertEqual(payload["recommended_classification_level"], "intimate")
        self.assertEqual(payload["detected_sources"][0]["selected"], True)
        self.assertEqual(payload["detected_sources"][0]["path"], str(export_large))
        section_map = {item["section"]: item for item in payload["section_breakdown"]}
        self.assertEqual(section_map["inbox"]["thread_count"], 2)
        self.assertEqual(section_map["message_requests"]["thread_count"], 1)
        counterpart_names = [item["name"] for item in payload["top_counterparts"]]
        self.assertEqual(counterpart_names[:2], ["Alice Example", "Dana Request"])
        self.assertEqual(payload["top_group_threads"][0]["title"], "Project Circle")
        self.assertIn("relationship-recency", payload["clone_foundation"][0])

    def test_dialogue_corpus_route_supports_chatgpt_export_json(self) -> None:
        export_path = self.root / "conversations.json"
        export_path.write_text(
            json.dumps(
                [
                    {
                        "conversation_id": "conv-1",
                        "id": "conv-1",
                        "mapping": {
                            "sys": {
                                "message": {
                                    "author": {"role": "system"},
                                    "content": {"parts": [""]},
                                    "create_time": None,
                                    "metadata": {},
                                }
                            },
                            "user": {
                                "message": {
                                    "author": {"role": "user"},
                                    "content": {"parts": ["Summarize my work style and goals."]},
                                    "create_time": 1_700_500_000.0,
                                    "metadata": {},
                                }
                            },
                            "assistant": {
                                "message": {
                                    "author": {"role": "assistant"},
                                    "content": {"parts": ["You are analytical and structured."]},
                                    "create_time": 1_700_500_010.0,
                                    "metadata": {"model_slug": "gpt-4"},
                                }
                            },
                        },
                    }
                ]
            ),
            encoding="utf-8",
        )

        app = create_app(self._settings_for("phase_2b_6_chatgpt.sqlite"))
        observed = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path="/api/dialogue-corpus/analyze",
                body={"source_path": str(export_path)},
            )
        )

        self.assertEqual(observed["status_code"], 200)
        payload = observed["json"]
        self.assertEqual(payload["source_kind"], "chatgpt_conversations_export")
        self.assertEqual(payload["thread_count"], 1)
        self.assertEqual(payload["sent_message_count"], 1)
        self.assertEqual(payload["received_message_count"], 2)
        self.assertEqual(payload["counterpart_count"], 0)
        self.assertIn("not human-to-human relationship edges", payload["relationship_priors"][0])
        self.assertEqual(payload["detected_sources"][0]["record_count"], 1)

    def test_v1_capabilities_expose_dialogue_corpus_capability(self) -> None:
        app = create_app(self._settings_for("phase_2b_6_caps.sqlite"))
        observed = asyncio.run(self._perform_request(app, method="GET", path="/v1/capabilities"))

        self.assertEqual(observed["status_code"], 200)
        payload = observed["json"]
        service_ids = {item["id"] for item in payload["services"]}
        self.assertIn("dialogue-corpus-service", service_ids)
        capability_map = {item["id"]: item for item in payload["capabilities"]}
        self.assertEqual(capability_map["dialogue.corpus.analyze"]["path"], "/api/dialogue-corpus/analyze")
        self.assertEqual(capability_map["dialogue.corpus.analyze"]["methods"], ["POST"])
        self.assertTrue(capability_map["dialogue.corpus.analyze"]["read_only"])
        self.assertFalse(capability_map["dialogue.corpus.analyze"]["room_scoped"])

    def test_dialogue_corpus_ui_copy_is_present(self) -> None:
        html = (PROJECT_ROOT / "src" / "klone" / "static" / "index.html").read_text(encoding="utf-8")
        js = (PROJECT_ROOT / "src" / "klone" / "static" / "app.js").read_text(encoding="utf-8")
        self.assertIn("Dialogue Corpus", html)
        self.assertIn("dialogue-corpus-form", html)
        self.assertIn("renderDialogueCorpus", js)
        self.assertIn("/api/dialogue-corpus/analyze", js)

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
        return Settings(
            app_name="Klone Phase 2B.6 Test",
            environment="test",
            owner_debug_mode=True,
            project_root=PROJECT_ROOT,
            data_dir=self.root / "data",
            sqlite_path=self.root / database_name,
            asset_preview_limit=12,
            audit_preview_limit=9,
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
        thread_dir = (
            export_root
            / "your_facebook_activity"
            / "messages"
            / section
            / slug
        )
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

    def _write_group_thread(
        self,
        export_root: Path,
        *,
        section: str,
        slug: str,
        title: str,
        participants: list[str],
        messages: list[dict[str, object]],
    ) -> None:
        thread_dir = (
            export_root
            / "your_facebook_activity"
            / "messages"
            / section
            / slug
        )
        thread_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "title": title,
            "thread_path": f"{section}/{slug}",
            "is_still_participant": True,
            "participants": [{"name": name} for name in participants],
            "messages": messages,
        }
        (thread_dir / "message_1.json").write_text(json.dumps(payload), encoding="utf-8")

    @staticmethod
    def _fb_message(
        sender_name: str,
        timestamp_ms: int,
        content: str,
        *,
        photos: list[dict[str, object]] | None = None,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "sender_name": sender_name,
            "timestamp_ms": timestamp_ms,
            "content": content,
            "is_geoblocked_for_viewer": False,
        }
        if photos:
            payload["photos"] = photos
        return payload


if __name__ == "__main__":
    unittest.main()
