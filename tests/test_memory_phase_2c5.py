from __future__ import annotations

import sys
from pathlib import Path
import tempfile
import unittest

from fastapi import HTTPException


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from klone.api import (  # noqa: E402
    memory_context_answer,
    memory_context_package,
    memory_context_payload,
)
from klone.ingest import ingest_dataset  # noqa: E402
from klone.memory import system_ingest_episode_id  # noqa: E402
from klone.repository import KloneRepository  # noqa: E402
from klone.schemas import (  # noqa: E402
    DatasetIngestRequest,
    MemoryContextPackageRecord,
    MemoryLlmAnswerRecord,
    MemoryLlmContextPayloadRecord,
)


class MemoryPhase2C5Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.repository = KloneRepository(self.root / "phase_2c5.sqlite")
        self.repository.initialize()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_memory_context_routes_return_read_only_models(self) -> None:
        result = self._ingest_dataset(
            label="Memory Explorer Route",
            classification_level="personal",
            folder_name="memory_explorer_route",
            files={"note.txt": "alpha"},
        )
        room_id = "restricted-room"
        episode_id = system_ingest_episode_id(room_id=room_id, ingest_run_id=result["run"]["id"])

        context_package = memory_context_package(
            room_id=room_id,
            event_id=None,
            episode_id=episode_id,
            repository=self.repository,
        )
        context_payload = memory_context_payload(
            room_id=room_id,
            event_id=None,
            episode_id=episode_id,
            repository=self.repository,
        )
        answer = memory_context_answer(
            question="Summarize this episode",
            room_id=room_id,
            event_id=None,
            episode_id=episode_id,
            repository=self.repository,
        )

        self.assertIsInstance(context_package, MemoryContextPackageRecord)
        self.assertIsInstance(context_payload, MemoryLlmContextPayloadRecord)
        self.assertIsInstance(answer, MemoryLlmAnswerRecord)
        self.assertEqual(context_package.room_id, room_id)
        self.assertEqual(context_package.query_scope.primary_episode_id, episode_id)
        self.assertEqual(context_payload.query_scope.primary_episode_id, episode_id)
        self.assertEqual(answer.query_scope.primary_episode_id, episode_id)
        self.assertFalse(context_payload.memory_write_enabled)
        self.assertFalse(answer.memory_write_enabled)
        self.assertEqual(answer.question, "Summarize this episode")
        self.assertTrue(answer.supported)
        self.assertFalse(answer.llm_call_performed)
        self.assertGreaterEqual(len(answer.source_backed_content), 1)

    def test_memory_context_routes_stay_room_scoped_and_validate_scope(self) -> None:
        restricted_result = self._ingest_dataset(
            label="Restricted Scope",
            classification_level="personal",
            folder_name="restricted_scope",
            files={"note.txt": "alpha"},
        )
        room_id = "restricted-room"
        episode_id = system_ingest_episode_id(
            room_id=room_id,
            ingest_run_id=restricted_result["run"]["id"],
        )

        with self.assertRaises(HTTPException) as both_missing:
            memory_context_package(
                room_id=room_id,
                event_id=None,
                episode_id=None,
                repository=self.repository,
            )
        self.assertEqual(both_missing.exception.status_code, 400)

        with self.assertRaises(HTTPException) as wrong_room:
            memory_context_payload(
                room_id="public-room",
                event_id=None,
                episode_id=episode_id,
                repository=self.repository,
            )
        self.assertEqual(wrong_room.exception.status_code, 404)

    def test_memory_explorer_ui_text_is_present(self) -> None:
        html = (PROJECT_ROOT / "src" / "klone" / "static" / "index.html").read_text(encoding="utf-8")
        self.assertIn("Memory Explorer", html)
        self.assertIn("Context and Read-Only Answer", html)

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


if __name__ == "__main__":
    unittest.main()
