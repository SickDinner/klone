from __future__ import annotations

import asyncio
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import sys
from pathlib import Path
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from klone.cli import main as cli_main  # noqa: E402
from klone.config import Settings  # noqa: E402
from klone.main import create_app  # noqa: E402


class Phase2B7Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.meta_root = self.root / "META"
        self._seed_export(self.meta_root / "facebook-export-large")

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_dialogue_corpus_answer_route_returns_top_counterparts(self) -> None:
        app = create_app(self._settings_for("phase_2b_7.sqlite"))
        observed = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path="/api/dialogue-corpus/answer",
                body={
                    "source_path": str(self.meta_root),
                    "question": "Keiden kanssa olen puhunut eniten?",
                },
            )
        )

        self.assertEqual(observed["status_code"], 200)
        payload = observed["json"]
        self.assertEqual(payload["answer_version"], "2b.7.bounded_dialogue_query_shell")
        self.assertEqual(payload["query_kind"], "top_counterparts")
        self.assertTrue(payload["supported"])
        self.assertIn("Alice Example", payload["source_backed_content"][0]["content"])

    def test_dialogue_corpus_answer_route_supports_named_counterpart_lookup(self) -> None:
        app = create_app(self._settings_for("phase_2b_7_lookup.sqlite"))
        observed = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path="/api/dialogue-corpus/answer",
                body={
                    "source_path": str(self.meta_root),
                    "question": 'Mitä tiedät "Alice Example" tämän korpuksen perusteella?',
                },
            )
        )

        self.assertEqual(observed["status_code"], 200)
        payload = observed["json"]
        self.assertEqual(payload["query_kind"], "counterpart_lookup")
        self.assertTrue(payload["supported"])
        self.assertIn("Alice Example appears in 1 direct thread", payload["source_backed_content"][0]["content"])

    def test_dialogue_corpus_answer_route_blocks_unbounded_semantic_question(self) -> None:
        app = create_app(self._settings_for("phase_2b_7_unsupported.sqlite"))
        observed = asyncio.run(
            self._perform_request(
                app,
                method="POST",
                path="/api/dialogue-corpus/answer",
                body={
                    "source_path": str(self.meta_root),
                    "question": "What trauma patterns and deep psychological conflicts do these chats reveal?",
                },
            )
        )

        self.assertEqual(observed["status_code"], 200)
        payload = observed["json"]
        self.assertEqual(payload["query_kind"], "unsupported")
        self.assertFalse(payload["supported"])
        self.assertIn("Supported bounded queries currently cover", payload["limitations"][-1])
        self.assertGreaterEqual(len(payload["suggested_queries"]), 3)

    def test_v1_capabilities_expose_dialogue_corpus_answer_capability(self) -> None:
        app = create_app(self._settings_for("phase_2b_7_caps.sqlite"))
        observed = asyncio.run(self._perform_request(app, method="GET", path="/v1/capabilities"))

        self.assertEqual(observed["status_code"], 200)
        capability_map = {item["id"]: item for item in observed["json"]["capabilities"]}
        self.assertEqual(capability_map["dialogue.corpus.answer"]["path"], "/api/dialogue-corpus/answer")
        self.assertEqual(capability_map["dialogue.corpus.answer"]["methods"], ["POST"])
        self.assertTrue(capability_map["dialogue.corpus.answer"]["read_only"])

    def test_cli_outputs_bounded_answer(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = cli_main(
                [
                    "--source",
                    str(self.meta_root),
                    "Keiden kanssa olen puhunut eniten?",
                ]
            )

        self.assertEqual(exit_code, 0, stderr.getvalue())
        rendered = stdout.getvalue()
        self.assertIn("Supported: yes", rendered)
        self.assertIn("Alice Example", rendered)
        self.assertIn("Evidence:", rendered)

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
                "client": ("127.0.0.1", 50011),
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
            app_name="Klone Phase 2B.7 Test",
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
        self._write_group_thread(
            export_root,
            section="inbox",
            slug="project_circle_1",
            title="Project Circle",
            participants=["Ville Olavi Peuho", "Bob Example", "Cara Example"],
            messages=[
                self._fb_message("Bob Example", 1_701_200_000_000, "Can we meet this week?"),
                self._fb_message("Ville Olavi Peuho", 1_701_200_100_000, "Yes, Thursday works."),
                self._fb_message("Cara Example", 1_701_200_200_000, "Thursday works for me too."),
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
        thread_dir = export_root / "your_facebook_activity" / "messages" / section / slug
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
    def _fb_message(sender_name: str, timestamp_ms: int, content: str) -> dict[str, object]:
        return {
            "sender_name": sender_name,
            "timestamp_ms": timestamp_ms,
            "content": content,
            "is_geoblocked_for_viewer": False,
        }


if __name__ == "__main__":
    unittest.main()
