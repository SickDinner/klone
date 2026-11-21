"""Knowledge Atlas API and Council72 public-source bridge tests.

Runs with mock local Wikipedia sources only. No Wikimedia, GPT or private
memory calls. Tests isolate FastAPI router from KLONE's main Memory Core.
"""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from klone.knowledge_atlas import Atlas
from klone.knowledge_atlas_bridge import (
    read_only_council_packet, _report_digest, main as bridge_main
)
from klone.knowledge_atlas_topics import ROLE_TOPICS, profiles
from klone.knowledge_atlas_api import router

NOW = "2026-11-01T12:30:05Z"


def page(n, title, body):
    return {
        "language": "en", "page_id": n, "title": title,
        "revision_id": n + 100, "revision_at": NOW,
        "content": body, "content_kind": "api_plaintext_extract"
    }


class KnowledgeAtlasBridgeApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "atlas"
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def _populate(self):
        with Atlas(self.root) as a:
            a.ingest(page(
                50, "Linguistics", "Linguistics is a scientific study of language."
            ), seed_member=24)
            a.ingest(page(
                55, "Scientific method",
                "Scientific method forms theories and makes predictions."
            ), seed_member=55)
            a.ingest(page(
                66, "Graph theory",
                "Graphs are mathematical structures in computer science."
            ), seed_member=65)

    def test_get_status_does_not_create_database_on_uninitialized_app(self):
        with patch("klone.knowledge_atlas_api.DEFAULT_ROOT", self.root):
            response = self.client.get("/api/knowledge-atlas/status")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["installed"])
        self.assertEqual(response.json()["distinct_article_count"], 0)
        self.assertFalse((self.root / "wikipedia.sqlite3").exists())

    def test_members_api_uses_original_council72_catalog(self):
        response = self.client.get("/api/knowledge-atlas/members")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["members"]), 72)
        specific = self.client.get("/api/knowledge-atlas/members/24")
        self.assertEqual(specific.status_code, 200)
        self.assertEqual(specific.json()["name"], "Naberius")
        self.assertEqual(specific.json()["canonical_task"],
                         "Kielten ja yleisöjen tulkkaus")
        self.assertFalse(specific.json()["memory_write_permission"])
        self.assertEqual(
            self.client.get("/api/knowledge-atlas/members/123").status_code,
            404
        )

    def test_api_search_uses_local_public_sources_only(self):
        self._populate()
        with patch("klone.knowledge_atlas_api.DEFAULT_ROOT", self.root):
            status = self.client.get("/api/knowledge-atlas/status")
            self.assertTrue(status.json()["installed"])
            self.assertEqual(status.json()["distinct_article_count"], 3)
            result = self.client.get(
                "/api/knowledge-atlas/search",
                params={"q": "scientific method", "member_id": 55, "limit": 4}
            )
            self.assertEqual(result.status_code, 200)
            d = result.json()
            self.assertEqual(d["source_count"], 1)
            self.assertTrue(d["matched_sources"][0]["specialist_seed_or_topic_hit"])
            self.assertEqual(d["model_api_requests"] if "model_api_requests" in d else 0, 0)
            self.assertFalse(d["memory_write"])

    def test_api_rejects_invalid_member_language_and_length(self):
        self._populate()
        with patch("klone.knowledge_atlas_api.DEFAULT_ROOT", self.root):
            self.assertEqual(
                self.client.get(
                    "/api/knowledge-atlas/search",
                    params={"q": "linguistics", "member_id": 73}
                ).status_code, 400
            )
            self.assertEqual(
                self.client.get(
                    "/api/knowledge-atlas/search",
                    params={"q": "linguistics", "language": "xx"}
                ).status_code, 400
            )
            self.assertEqual(
                self.client.get(
                    "/api/knowledge-atlas/search", params={"q": "x"}
                ).status_code, 422
            )

    def test_ring_packet_is_citation_bound_with_no_automatic_powers(self):
        self._populate()
        with Atlas(self.root) as a:
            result = read_only_council_packet(
                a, ring_id=1, question="linguistics", language="en"
            )
        self.assertEqual(result["member_count"], 8)
        self.assertEqual(result["ring_id"], 1)
        self.assertEqual(result["unique_citation_count"], 1)
        self.assertFalse(result["may_execute_source_instructions"])
        self.assertFalse(result["may_train_or_retrain_model"])
        self.assertFalse(result["may_write_main_memory"])
        self.assertFalse(result["may_modify_permissions"])
        self.assertEqual(result["model_api_requests"], 0)
        self.assertTrue(result["operator_review_required_before_model_use"])
        self.assertEqual(result["report_sha256"], _report_digest({
            k: v for k, v in result.items() if k != "report_sha256"
        }))
        self.assertIn("oldid=150", result["citation_sources"][0]["source_url"])

    def test_member_packet_has_exact_canonical_task_and_explicit_fallback(self):
        self._populate()
        with Atlas(self.root) as a:
            result = read_only_council_packet(
                a, member_id=65, question="zzznotarealsubject",
                language="en"
            )
        self.assertEqual(result["member_count"], 1)
        self.assertEqual(result["member_id"], 65)
        self.assertEqual(result["member_profiles"][0]["canonical_task"],
                         next(p["canonical_task"] for p in profiles()
                              if p["member_id"] == 65))
        self.assertTrue(
            result["member_profiles"][0]["topic_fallback_not_direct_question_evidence"]
        )

    def test_bad_scope_and_large_queries_fail_before_any_model(self):
        with Atlas(self.root) as a:
            for kwargs in (
                {"ring_id": 0, "question": "sample"},
                {"member_id": 100, "question": "sample"},
                {"ring_id": 1, "member_id": 24, "question": "sample"},
                {"question": "sample"},
                {"ring_id": 1, "question": "x"},
                {"ring_id": 1, "question": "x" * 201},
                {"ring_id": 1, "question": "sample", "per_member": 4},
            ):
                with self.assertRaises(ValueError):
                    read_only_council_packet(a, **kwargs)
            self.assertEqual(a.state()["distinct_article_count"], 0)

    def test_ring_endpoint_reads_but_never_writes_to_private_memory(self):
        self._populate()
        with patch("klone.knowledge_atlas_api.DEFAULT_ROOT", self.root):
            response = self.client.get(
                "/api/knowledge-atlas/council/1",
                params={"question": "linguistics", "language": "en"}
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["member_count"], 8)
            self.assertFalse(response.json()["may_write_main_memory"])
            self.assertEqual(
                self.client.get(
                    "/api/knowledge-atlas/council/0",
                    params={"question": "linguistics"}
                ).status_code, 400
            )

    def test_ring_packet_cli_writes_only_new_report(self):
        self._populate()
        report_path = Path(self.tmp.name) / "pub.json"
        with patch("klone.knowledge_atlas_bridge.Atlas") as cls:
            # No actual test-only model calls; use native Atlas constructor
            # to verify the CLI produces a separate read-only source packet.
            cls.side_effect = lambda *args, **kwargs: Atlas(self.root)
            bridge_main([
                "--root", str(self.root), "--member-id", "24",
                "--question", "linguistics", "--output", str(report_path)
            ])
        packet = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(packet["member_count"], 1)
        self.assertFalse(packet["may_write_main_memory"])
        self.assertEqual(packet["unique_citation_count"], 1)


if __name__ == "__main__":
    unittest.main()
