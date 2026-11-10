from __future__ import annotations

import unittest

from klone.hypervisor_dispatch import DispatchDenied
from klone.research_agent import ResearchAgent, ResearchSource


class ResearchAgentTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.sources = [
            ResearchSource("a", "DNA chronology", "Ancient DNA samples were compared.", "public-room", "public", "archive:a"),
            ResearchSource("b", "DNA restricted", "Private DNA profile is secret.", "restricted-room", "restricted_bio", "archive:b"),
            ResearchSource("c", "Music", "Music composition and harmony.", "public-room", "public", "archive:c"),
        ]
        self.agent = ResearchAgent(
            sources=self.sources,
            audit=lambda event, route, seam: self.events.append(event),
            authorize_output=lambda level: "allowed" if level == "public" else "blocked",
        )

    def query(self, **changes):
        args = dict(question="DNA samples", room_id="public-room", actor_role="owner",
                    trace_id="research-1", classification_level="public")
        args.update(changes)
        return self.agent.search(**args)

    def test_cited_retrieval_is_room_scoped(self):
        result = self.query().payload
        self.assertEqual(result["source_count"], 1)
        self.assertEqual(result["results"][0]["reference"], "archive:a")
        self.assertNotIn("Private", str(result))
        self.assertEqual(self.events, ["delegated", "completed"])

    def test_denied_room_never_retrieves(self):
        with self.assertRaises(DispatchDenied):
            self.query(room_id="unknown")
        self.assertEqual(self.events, ["denied"])

    def test_restricted_classification_denied(self):
        with self.assertRaises(DispatchDenied):
            self.query(room_id="restricted-room", classification_level="restricted_bio")

    def test_empty_and_overlong_question_rejected(self):
        for question in ("", "x" * 501):
            with self.assertRaises(ValueError):
                self.query(question=question)

    def test_duplicate_provenance_rejected(self):
        with self.assertRaises(ValueError):
            ResearchAgent(sources=self.sources + self.sources[:1],
                          audit=lambda *args: None, authorize_output=lambda _: "allowed")

    def test_no_matching_sources_does_not_invent_answer(self):
        result = self.query(question="volcanology").payload
        self.assertEqual(result["results"], [])
        self.assertEqual(result["source_count"], 0)

    def test_audit_failure_prevents_search(self):
        agent = ResearchAgent(sources=self.sources,
                              audit=lambda *args: (_ for _ in ()).throw(OSError("audit down")),
                              authorize_output=lambda _: "allowed")
        with self.assertRaises(OSError):
            agent.search(question="DNA", room_id="public-room", actor_role="owner",
                         trace_id="research-fail", classification_level="public")


if __name__ == "__main__":
    unittest.main()
