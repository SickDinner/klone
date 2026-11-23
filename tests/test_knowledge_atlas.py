"""Knowledge Atlas unit tests. Zero Wikimedia/GPT requests and no Memory writes."""
from __future__ import annotations

import bz2
from hashlib import sha256
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import shutil
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from klone.council72 import catalog
from klone.knowledge_atlas import (
    Atlas, AtlasError, MAX_ARTICLES_HARD, MAX_TEXT_CHARS,
    _api_pages, _fts_tokens, _mediawiki_request, _prepared_article,
    collect, import_local_dump, main,
)
from klone.knowledge_atlas_topics import (
    LANGUAGES, ROLE_TOPICS, TARGET_UNIQUE_ARTICLES,
    SHARED_FOUNDATIONS, PHASES, plan, profiles
)

NOW = "2026-11-01T12:30:05Z"


def article(page_id=1, title="Linguistics", revision_id=100,
            revision_at=NOW, content="Linguistics is the scientific study of language.",
            language="en", content_kind="api_plaintext_extract"):
    return {
        "language": language, "page_id": page_id, "title": title,
        "revision_id": revision_id, "revision_at": revision_at,
        "content": content, "content_kind": content_kind
    }


def xml_page(page_id, title, *, ns=0, redirect=False):
    x = f"<redirect title='Elsewhere'/>" if redirect else ""
    return (f"<page><title>{title}</title><ns>{ns}</ns><id>{page_id}</id>"
            f"{x}<revision><id>{page_id+500}</id>"
            f"<timestamp>{NOW}</timestamp><text xml:space='preserve'>"
            f"= {title} =\nOpen source encyclopedia article {title}."
            "</text></revision></page>")


class KnowledgeAtlasTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.atlas = Atlas(self.root / "public")
        self.addCleanup(self.atlas.db.close)

    def test_all_72_canonical_profiles_have_distinct_lanes(self):
        data = plan()
        self.assertEqual(data["total_role_profiles"], 72)
        self.assertEqual(data["topic_queries_total"], 216)
        self.assertEqual(data["target_distinct_pages"], 72_000)
        self.assertEqual(data["phases_distinct_pages"][-1], 72_000)
        self.assertEqual(len(SHARED_FOUNDATIONS), 32)
        self.assertEqual(len(data["profiles"]), 72)
        self.assertEqual({p["member_id"] for p in data["profiles"]},
                         set(range(1, 73)))
        original = {m["id"]: m for m in catalog()["members"]}
        for member in data["profiles"]:
            self.assertEqual(member["canonical_task"],
                             original[member["member_id"]]["task"])
            self.assertEqual(member["ring_id"],
                             original[member["member_id"]]["ring"])
            self.assertEqual(member["founder"],
                             original[member["member_id"]]["founder"])
            self.assertEqual(len(member["expertise_topics"]), 3)
            self.assertFalse(member["memory_write_permission"])
        self.assertFalse(data["no_articles_downloaded_by_plan"] is False)

    def test_plan_does_not_claim_downloaded_articles(self):
        self.assertTrue(plan()["no_articles_downloaded_by_plan"])
        self.assertEqual(self.atlas.state()["distinct_article_count"], 0)
        self.assertEqual(self.atlas.state()["indexed_member_coverage"], 0)

    def test_complete_72_member_coverage_discloses_weak_vs_seeded_links(self):
        before = self.atlas.member_coverage()
        self.assertEqual(len(before["member_profiles"]), 72)
        self.assertEqual(before["members_with_any_article"], 0)
        self.assertEqual(len(before["members_without_article_links"]), 72)
        self.atlas.ingest(article(), seed_member=24)
        self.atlas.ingest(article(page_id=3, title="Topology",
                                  content="Topology studies connected spaces."))
        after = self.atlas.member_coverage()
        member = {x["member_id"]:x for x in after["member_profiles"]}
        self.assertEqual(member[24]["pages_from_explicit_role_queries"], 1)
        self.assertEqual(member[24]["pages_from_weak_keyword_hints"], 0)
        self.assertEqual(member[65]["pages_from_weak_keyword_hints"], 1)
        self.assertFalse(member[65]["expertise_established_by_count"])
        self.assertFalse(after["memory_write"])
        self.assertFalse(after["retrieval_index_not_scientific_verification"] is False)

    def test_wikipedia_attribution_and_revision_are_preserved(self):
        self.assertEqual(self.atlas.ingest(article()), "inserted")
        result = self.atlas.search("linguistics", member_id=24)
        self.assertEqual(result["source_count"], 1)
        found = result["matched_sources"][0]
        self.assertEqual(found["revision_id"], 100)
        self.assertIn("oldid=100", found["source_url"])
        self.assertIn("title=Linguistics&action=history", found["attribution_url"])
        self.assertIn("CC BY-SA", found["license_name"])
        self.assertIn("creative", found["license_url"])
        self.assertEqual(found["content_kind"], "api_plaintext_extract")
        self.assertFalse(found["source_truth_verified"])
        self.assertFalse(result["memory_write"])
        self.assertFalse(result["retrieval_only_no_model_call"] is False)

    def test_seeded_article_is_member_specific_without_duplication(self):
        self.assertEqual(self.atlas.ingest(article(), seed_member=24),
                         "inserted")
        self.assertEqual(self.atlas.ingest(article(), seed_member=27),
                         "unchanged")
        self.assertEqual(self.atlas.current_count(), 1)
        self.assertEqual(self.atlas.state()["member_article_links"], 2)
        self.assertTrue(self.atlas.search(
            "language", member_id=24
        )["matched_sources"][0]["specialist_seed_or_topic_hit"])

    def test_latest_revision_wins_and_old_revision_never_overwrites(self):
        self.atlas.ingest(article())
        a = article(revision_id=101, revision_at="2026-11-02T00:00:00Z",
                    content="Historical linguistics compares language change.")
        self.assertEqual(self.atlas.ingest(a), "updated")
        self.assertEqual(self.atlas.ingest(article()), "older_skipped")
        self.assertEqual(self.atlas.ingest(a), "unchanged")
        r = self.atlas.search("historical linguistics")
        self.assertEqual(r["source_count"], 1)
        self.assertEqual(r["matched_sources"][0]["revision_id"], 101)
        self.assertEqual(self.atlas.current_count(), 1)

    def test_multilingual_articles_do_not_overwrite_same_page_id(self):
        self.atlas.ingest(article())
        self.atlas.ingest(article(language="fi", title="Kielitiede",
                                  content="Kielitiede tarkastelee kieltä."))
        self.assertEqual(self.atlas.current_count(), 2)
        self.assertEqual(
            self.atlas.search("kielitiede", language="fi")["source_count"], 1
        )
        self.assertEqual(
            self.atlas.search("linguistics", language="en")["source_count"], 1
        )

    def test_truncation_is_explicit_and_hash_matches_exact_stored_content(self):
        a = article(content="language " * 4000)
        self.atlas.ingest(a)
        row = self.atlas.db.execute(
            "SELECT truncated,original_length_chars,stored_sha256 "
            "FROM articles LIMIT 1"
        ).fetchone()
        self.assertEqual(row["truncated"], 1)
        self.assertEqual(row["original_length_chars"], len(a["content"]))
        self.assertEqual(len(self.atlas.search(
            "language")["matched_sources"][0]["text_excerpt_untrusted"]), 450)

    def test_invalid_source_and_overlong_page_fail_closed(self):
        bad = article()
        bad["language"] = "xx"
        with self.assertRaisesRegex(AtlasError, "allowlisted"):
            self.atlas.ingest(bad)
        bad = article(content="x" * 12_000_001)
        with self.assertRaisesRegex(AtlasError, "oversized"):
            self.atlas.ingest(bad)
        bad = article(content="")
        with self.assertRaisesRegex(AtlasError, "empty"):
            self.atlas.ingest(bad)
        bad = article()
        bad["revision_id"] = 0
        with self.assertRaisesRegex(AtlasError, "revision ID"):
            self.atlas.ingest(bad)

    def test_fts_query_escapes_operators_and_no_sql_injection(self):
        self.atlas.ingest(article())
        with self.assertRaises(AtlasError):
            self.atlas.search("")
        with self.assertRaises(AtlasError):
            self.atlas.search("a" * 251)
        self.assertIsInstance(self.atlas.search("' or 1=1 --"), dict)
        self.assertEqual(self.atlas.current_count(), 1)

    def test_fallback_search_does_not_interpret_body_blob_as_text(self):
        self.atlas.ingest(article())
        self.atlas.fts_enabled = False
        response = self.atlas.search("linguistics")
        self.assertEqual(response["source_count"], 1)

    def test_disclosed_lexical_role_hints_do_not_fabricate_authority(self):
        self.atlas.ingest(article(title="Topology",
                                  content="Topology studies mathematical spaces."))
        r = self.atlas.search("topology", member_id=65)
        self.assertEqual(r["source_count"], 1)
        self.assertTrue(r["matched_sources"][0]["specialist_seed_or_topic_hit"])
        self.assertFalse(r["source_truth_verified"])

    def test_api_extract_parses_known_revision_and_skips_missing(self):
        payload = {
            "query": {"pages": [
                {"ns": 0, "pageid": 7, "title": "Biology",
                 "extract": "Biology studies life.",
                 "revisions": [{"revid": 15, "timestamp": NOW}]},
                {"ns": 0, "pageid": 8, "title": "Blank",
                 "extract": "", "revisions": [{"revid": 16, "timestamp": NOW}]},
                {"ns": 1, "pageid": 9, "title": "Talk:Bio",
                 "extract": "no", "revisions": [{"revid": 17, "timestamp": NOW}]},
            ]}
        }
        found = _api_pages(payload, "en")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["page_id"], 7)
        self.assertEqual(found[0]["revision_id"], 15)
        self.assertEqual(found[0]["content_kind"], "api_plaintext_extract")
        with self.assertRaises(AtlasError):
            _api_pages({"error": {"code": "maxlag"}}, "en")

    def test_explicit_network_gate_zero_request_by_default(self):
        with self.assertRaises(SystemExit):
            main(["--root", str(self.root / "none"), "collect",
                  "--requests", "1"])
        with self.assertRaises(AtlasError):
            _mediawiki_request("en", "Biology", user_agent="KLONE")

    def test_mocked_mediawiki_collection_is_bounded_and_resumable(self):
        calls = []
        def sender(language, query, *, user_agent):
            calls.append((language, query, user_agent))
            return {
                "query": {"pages": [{
                    "ns": 0, "pageid": 7, "title": "Biology",
                    "extract": "Biology studies life.",
                    "revisions": [{"revid": 15, "timestamp": NOW}]
                }]}
            }
        kwargs = {"language": "fi", "requests": 2,
                  "user_agent": "KLONE/0.1 (https://github.com/SickDinner/klone)",
                  "delay": 1.5, "sender": sender}
        with patch("klone.knowledge_atlas.time.sleep") as asleep:
            answer = collect(self.atlas, **kwargs)
        self.assertEqual(answer["api_requests"], 2)
        self.assertEqual(self.atlas.get_cursor("fi"), 2)
        self.assertEqual(self.atlas.current_count(), 1)
        # First 32 queries are SHARED foundations, not misattributed
        # to a specialist just to inflate member coverage.
        self.assertEqual(self.atlas.state()["member_article_links"], 0)
        self.assertEqual(len(calls), 2)
        asleep.assert_called_once()
        with patch("klone.knowledge_atlas.time.sleep"):
            collect(self.atlas, **kwargs)
        self.assertEqual(self.atlas.get_cursor("fi"), 4)
        self.assertEqual(self.atlas.current_count(), 1)
        with self.assertRaisesRegex(AtlasError, "request count"):
            collect(self.atlas, **{**kwargs, "requests": 13})

    def test_api_error_does_not_advance_cursor_or_autoretry(self):
        calls = []
        def failure(language, query, *, user_agent):
            calls.append(query)
            raise AtlasError("Wikimedia is rate-limiting or busy")
        with self.assertRaisesRegex(AtlasError, "rate-limiting"):
            collect(self.atlas, language="fi", requests=2,
                    delay=1.5, user_agent="KLONE-contact",
                    sender=failure)
        self.assertEqual(self.atlas.get_cursor("fi"), 0)
        self.assertEqual(len(calls), 1)

    def test_offline_dump_import_streams_only_main_namespace(self):
        xml = "<?xml version='1.0' encoding='utf-8'?><mediawiki>" + (
            xml_page(10, "Astronomy") +
            xml_page(11, "Talk:Nope", ns=1) +
            xml_page(12, "Redirect", redirect=True) +
            xml_page(13, "Genetics")
        ) + "</mediawiki>"
        dump = self.root / "fiwiki-small.xml.bz2"
        dump.write_bytes(bz2.compress(xml.encode("utf-8")))
        result = import_local_dump(self.atlas, dump, language="fi",
                                   max_pages=1)
        self.assertEqual(result["articles_inserted"], 1)
        self.assertEqual(result["stopped_at_scan_offset"], 1)
        self.assertEqual(self.atlas.current_count(), 1)
        self.assertFalse(result["input_file_sha256_verified"])
        nextpart = import_local_dump(self.atlas, dump, language="fi",
                                     max_pages=1, skip_pages=1)
        self.assertEqual(nextpart["articles_inserted"], 1)
        self.assertEqual(nextpart["stopped_at_scan_offset"], 2)
        self.assertEqual(self.atlas.current_count(), 2)
        record = self.atlas.search("astronomy")
        self.assertEqual(record["source_count"], 1)
        self.assertEqual(record["matched_sources"][0]["content_kind"],
                         "dump_wikitext")

    def test_verified_official_dump_sha256_checked_before_import(self):
        xml = ("<?xml version='1.0'?><mediawiki>" +
               xml_page(90, "Natural sciences") + "</mediawiki>")
        path = self.root / "verified-export.xml.bz2"
        path.write_bytes(bz2.compress(xml.encode("utf-8")))
        expected = sha256(path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(AtlasError, "SHA256 mismatch"):
            import_local_dump(self.atlas, path, language="en",
                              expected_sha256="0" * 64)
        self.assertEqual(self.atlas.current_count(), 0)
        result = import_local_dump(self.atlas, path, language="en",
                                   expected_sha256=expected)
        self.assertTrue(result["input_file_sha256_verified"])
        self.assertEqual(result["input_file_sha256"], expected)
        self.assertEqual(result["articles_inserted"], 1)
        with self.assertRaisesRegex(AtlasError, "64 hex"):
            import_local_dump(self.atlas, path, language="en",
                              expected_sha256="not-a-hash")

    def test_doctype_and_entity_xml_are_refused(self):
        evil = self.root / "unsafe.xml"
        evil.write_text(
            '<!DOCTYPE foo [<!ENTITY x "wrong">]><mediawiki></mediawiki>',
            encoding="utf-8"
        )
        with self.assertRaisesRegex(AtlasError, "DOCTYPE"):
            import_local_dump(self.atlas, evil, language="en")

    def test_dump_does_not_accept_arbitrary_binary_or_absurd_limits(self):
        bad = self.root / "unsafe.exe"
        bad.write_bytes(b"not XML")
        with self.assertRaisesRegex(AtlasError, "require local Wikimedia"):
            import_local_dump(self.atlas, bad, language="en")
        with self.assertRaisesRegex(AtlasError, "page count"):
            import_local_dump(self.atlas, bad, language="en", max_pages=20001)

    def test_database_is_separate_from_core_and_storage_is_bounded(self):
        s = self.atlas.state()
        self.assertTrue(s["public_corpus_separate_from_main_memory"])
        self.assertFalse(s["autonomous_authority"])
        self.assertFalse(s["memory_write"])
        self.assertEqual(s["storage_bytes_soft_limit"], 512 * 1024 * 1024)
        self.assertEqual(s["target_distinct_articles"], 72_000)
        self.assertEqual(s["phase_goals"], [2000, 12000, 30000, 72000])
        self.assertIn("wikipedia.sqlite3", str(self.atlas.path))

    def test_invalid_member_and_language_rejected(self):
        self.atlas.ingest(article())
        with self.assertRaisesRegex(AtlasError, "member"):
            self.atlas.search("linguistics", member_id=0)
        with self.assertRaisesRegex(AtlasError, "allowlisted"):
            self.atlas.search("linguistics", language="xx")
        with self.assertRaisesRegex(AtlasError, "member ID"):
            self.atlas.ingest(article(), seed_member=73)
        with self.assertRaisesRegex(AtlasError, "search limit"):
            self.atlas.search("linguistics", limit=31)

    def test_termux_script_syntax_and_separate_command_argument_rules(self):
        path = Path(__file__).resolve().parents[1] / (
            "scripts/klone-knowledge-atlas-phone.sh"
        )
        script = path.read_text(encoding="utf-8")
        self.assertIn("  collect)", script)
        self.assertIn("  import-dump)", script)
        self.assertIn("  ring)", script)
        self.assertIn("  coverage)", script)
        # Request-count check must not accidentally treat a dump language
        # or a ring question as an integer at script entry.
        self.assertNotIn('case "$REQUESTS" in',
                         script.split("case \"$MODE\" in")[0])
        # This script targets POSIX/Termux. Git Bash on Windows may be on PATH
        # but does not reliably support this stdin syntax-check invocation.
        # Linux CI still executes the real bash -n syntax check.
        if os.name != "nt" and shutil.which("bash"):
            syntax = subprocess.run(
                ["bash", "-n"],
                input=script,
                capture_output=True, text=True, check=False
            )
            self.assertEqual(syntax.returncode, 0, syntax.stderr)

    def test_search_finds_titles_and_reports_empty_outcome(self):
        self.atlas.ingest(article(title="Quantum mechanics",
                                  content="Physics models wavefunctions."))
        found = self.atlas.search("quantum", limit=4)
        self.assertEqual(found["source_count"], 1)
        self.assertEqual(self.atlas.search("unfindabletermz")["source_count"], 0)


if __name__ == "__main__":
    unittest.main()
