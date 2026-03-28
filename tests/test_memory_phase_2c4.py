from __future__ import annotations

import sys
from pathlib import Path
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from klone.ingest import ingest_dataset  # noqa: E402
from klone.memory import MemoryService, system_ingest_episode_id  # noqa: E402
from klone.repository import KloneRepository  # noqa: E402
from klone.schemas import DatasetIngestRequest, MemoryLlmAnswerRecord  # noqa: E402


class MemoryPhase2C4Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.repository = KloneRepository(self.root / "phase_2c4.sqlite")
        self.repository.initialize()
        self.memory_service = MemoryService(self.repository)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_read_only_llm_answer_is_source_linked_and_deterministic(self) -> None:
        result = self._ingest_dataset(
            label="Episode LLM Answer",
            classification_level="personal",
            folder_name="episode_llm_answer",
            files={"note.txt": "alpha"},
        )
        room_id = "restricted-room"
        ingest_run_id = result["run"]["id"]
        episode_id = system_ingest_episode_id(room_id=room_id, ingest_run_id=ingest_run_id)

        run_events = self.repository.list_memory_events(
            room_id=room_id,
            limit=50,
            offset=0,
            ingest_run_id=ingest_run_id,
        )
        ingest_started = next(row for row in run_events if row["event_type"] == "ingest_started")
        ingest_completed = next(row for row in run_events if row["event_type"] == "ingest_completed")

        self.memory_service.reject_episode(
            room_id=room_id,
            episode_id=episode_id,
            reason="llm_answer_episode_reject",
        )
        self.memory_service.supersede_event(
            room_id=room_id,
            event_id=ingest_started["id"],
            superseded_by_event_id=ingest_completed["id"],
            reason="llm_answer_supersede",
        )

        counts_before = self.repository.counts_for_room(room_id=room_id)
        internal_runs_before = self.repository.list_internal_runs(limit=20)

        def answerer(_prompt: str, context_payload) -> dict:
            refs = context_payload.context_package.provenance_summary.source_refs
            return {
                "source_backed_content": [
                    {
                        "content": (
                            f"Episode {context_payload.query_scope.primary_episode_id} includes "
                            f"{len(context_payload.context_package.included_events)} linked events."
                        ),
                        "source_refs": refs,
                    }
                ],
                "derived_explanation": "The deterministic context shows a bounded ingest episode and its linked events.",
                "uncertainty": [
                    "This answer is limited to the selected room-scoped context package.",
                ],
            }

        answer_once = self.memory_service.generate_read_only_llm_answer(
            room_id=room_id,
            episode_id=episode_id,
            question="Summarize this episode",
            answerer=answerer,
        )
        answer_twice = self.memory_service.generate_read_only_llm_answer(
            room_id=room_id,
            episode_id=episode_id,
            question="Summarize this episode",
            answerer=answerer,
        )

        counts_after = self.repository.counts_for_room(room_id=room_id)
        internal_runs_after = self.repository.list_internal_runs(limit=20)

        self.assertIsInstance(answer_once, MemoryLlmAnswerRecord)
        self.assertEqual(answer_once.model_dump(), answer_twice.model_dump())
        self.assertEqual(counts_before, counts_after)
        self.assertEqual(internal_runs_before, internal_runs_after)
        self.assertTrue(answer_once.supported)
        self.assertTrue(answer_once.llm_call_performed)
        self.assertFalse(answer_once.memory_write_enabled)
        self.assertEqual(answer_once.query_scope.scope_kind, "episode_detail")
        self.assertEqual(answer_once.query_scope.primary_episode_id, episode_id)
        self.assertEqual(len(answer_once.source_backed_content), 1)
        self.assertEqual(
            answer_once.source_backed_content[0].source_refs,
            answer_once.context_payload.context_package.provenance_summary.source_refs,
        )
        self.assertEqual(
            [item.memory_id for item in answer_once.context_payload.included_context],
            [
                episode_id,
                str(ingest_started["id"]),
                str(ingest_completed["id"]),
            ],
        )
        self.assertIn("bounded_by_read_only_source_linked_memory", answer_once.limitations)

    def test_read_only_llm_answer_is_bounded_for_unsupported_questions(self) -> None:
        result = self._ingest_dataset(
            label="Unsupported LLM Answer",
            classification_level="personal",
            folder_name="unsupported_llm_answer",
            files={"note.txt": "alpha"},
        )
        room_id = "restricted-room"
        episode_id = system_ingest_episode_id(room_id=room_id, ingest_run_id=result["run"]["id"])

        answer = self.memory_service.generate_read_only_llm_answer(
            room_id=room_id,
            episode_id=episode_id,
            question="What should I do next?",
        )

        self.assertFalse(answer.supported)
        self.assertFalse(answer.llm_call_performed)
        self.assertFalse(answer.memory_write_enabled)
        self.assertEqual(answer.source_backed_content, [])
        self.assertIsNone(answer.derived_explanation)
        self.assertIn(
            "unsupported_question_for_bounded_read_only_answer_path",
            answer.limitations,
        )

    def test_read_only_llm_answer_preserves_room_isolation(self) -> None:
        restricted_result = self._ingest_dataset(
            label="Restricted LLM Answer",
            classification_level="personal",
            folder_name="restricted_llm_answer",
            files={"note.txt": "alpha"},
        )
        self._ingest_dataset(
            label="Public LLM Answer",
            classification_level="public",
            folder_name="public_llm_answer",
            files={"note.txt": "beta"},
        )

        restricted_room_id = "restricted-room"
        public_room_id = "public-room"
        restricted_episode_id = system_ingest_episode_id(
            room_id=restricted_room_id,
            ingest_run_id=restricted_result["run"]["id"],
        )

        with self.assertRaises(ValueError):
            self.memory_service.generate_read_only_llm_answer(
                room_id=public_room_id,
                episode_id=restricted_episode_id,
                question="Summarize this episode",
            )

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
