"""Limbo external research: fixed public feeds, eight existing couriers and no posting."""
import copy
import json
import unittest
from unittest.mock import patch, MagicMock
from urllib.parse import urlencode

from fastapi.testclient import TestClient

from klone.council72 import catalog
from klone.limbo_external import (
    BY_ID, FEEDS, ARXIV_RECENT_CATEGORIES, agents, analyze_documents,
    draft_question, fetch_source, fetch_recent_arxiv, parse_feed,
    validate_documents, main,
)
from klone.main import create_app


def sample(source_id="arxiv-ai", url="https://arxiv.org/abs/2601.01234"):
    return {
        "source_id": source_id, "courier_id": BY_ID[source_id].courier_id,
        "title": "Sample preprint on model memory",
        "summary": "A reported result, not an established finding.",
        "url": url, "published_at": "2026-11-15",
    }


class LimboExternalTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(create_app())

    def test_agent_roster_is_existing_council_ring_one_with_real_modulators(self):
        actual = [m for m in catalog()["members"] if m["ring"] == 1]
        rows = agents()
        self.assertEqual(len(rows), 8)
        self.assertEqual({a["id"] for a in rows}, {m["id"] for m in actual})
        self.assertEqual({a["id"] for a in rows}, {24, 27, 30, 53, 55, 70, 11, 71})
        for a in rows:
            m = next(m for m in actual if m["id"] == a["id"])
            self.assertEqual(a["founder_id"], m["courier_for"])
            self.assertEqual(a["baseline_modulators"], m["baseline_modulators"])
            self.assertEqual(len(a["baseline_modulators"]), 6)
            self.assertFalse(a["external_action"])
            self.assertIn("AI disclosure required", a["identity_policy"])

    def test_source_registry_is_fixed_and_distinct_by_courier(self):
        self.assertEqual(len(FEEDS), 8)
        self.assertEqual(len({f.id for f in FEEDS}), 8)
        self.assertEqual(len({f.courier_id for f in FEEDS}), 8)
        self.assertLess(len({f.publisher_group for f in FEEDS}), 8)
        for f in FEEDS:
            self.assertTrue(f.url.startswith("https://"))
            self.assertTrue(f.allowed_article_hosts)

    def test_rss_parse_bounded_and_html_stripping(self):
        feed = b"""<?xml version="1.0"?><rss version="2.0"><channel>
        <item><title>Science &amp; truth</title>
        <description>&lt;b&gt;New reported finding&lt;/b&gt;</description>
        <link>https://arxiv.org/abs/2601.01234</link><pubDate>Mon, 16 Nov 2026 00:00:00 GMT</pubDate></item>
        <item><title>Bad</title><description>Redirect to private</description>
        <link>http://127.0.0.1/admin</link></item></channel></rss>"""
        rows = parse_feed("arxiv-ai", feed)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "Science & truth")
        self.assertEqual(rows[0]["summary"], "New reported finding")
        self.assertEqual(rows[0]["courier_id"], 55)
        with self.assertRaises(ValueError):
            parse_feed("arxiv-ai", b"<!DOCTYPE x><rss/>")
        with self.assertRaises(ValueError):
            parse_feed("arxiv-ai", b"x" * (1024 * 1024 + 1))

    def test_atom_parse_and_safe_host_filter(self):
        feed = ("""<feed xmlns="http://www.w3.org/2005/Atom">
        <entry><title>New paper</title><link href="https://arxiv.org/abs/2601.99999"/>
        <summary>Summary text</summary><updated>2026-11-15T09:00:00Z</updated></entry>
        </feed>""").encode()
        self.assertEqual(parse_feed("arxiv-ai", feed)[0]["url"], "https://arxiv.org/abs/2601.99999")
        self.assertEqual(parse_feed("smithsonian-arts", feed), [])

    def test_reject_cross_courier_private_url_or_claims_of_authentication(self):
        valid = sample()
        for changes in (
            {"courier_id": 24},
            {"url": "http://arxiv.org/abs/123"},
            {"url": "https://localhost/private"},
            {"url": "https://127.0.0.1/"},
            {"url": "https://arxiv.org@127.0.0.1/private"},
            {"url": "https://arxiv.org/abs/123#secret"},
            {"extra": "untrusted"},
            {"classification": "sealed"},
        ):
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    validate_documents([{**valid, **changes}])
        with self.assertRaises(ValueError):
            validate_documents([valid, valid])
        with self.assertRaises(ValueError):
            validate_documents([valid] * 49)

    def test_preview_is_deterministic_and_never_marks_publisher_claim_verified(self):
        before = sample()
        input_rows = [before, sample("smithsonian-arts", "https://www.smithsonianmag.com/arts-culture/test/")]
        original = copy.deepcopy(input_rows)
        a = analyze_documents(input_rows)
        b = analyze_documents(input_rows)
        self.assertEqual(a, b)
        self.assertEqual(input_rows, original)
        self.assertEqual(len(a["agent_reports"]), 8)
        self.assertFalse(a["sources_are_verified"])
        self.assertFalse(a["facts_are_verified"])
        self.assertFalse(a["authority"]["posting"])
        self.assertFalse(a["authority"]["external_actions"])
        self.assertEqual(a["session_request"]["classification"], "public")
        self.assertEqual(a["session_request"]["source_kind"], "user_claims")
        for obs in a["session_request"]["steps"][0]["observations"]:
            self.assertEqual(obs["stance"], "unknown")
            self.assertEqual(obs["classification"], "public")
            self.assertEqual(obs["signals"]["uncertainty"], 1.0)

    def test_question_draft_is_disclosed_unsent_and_not_impersonation(self):
        d = draft_question(courier_id=55, source_id="arxiv-ai", question="Mikä oli tutkimuksen otoskoko")
        self.assertIn("automaattinen tutkimusagentti", d["message"])
        self.assertIn("Orobas", d["message"])
        self.assertFalse(d["send_ready"])
        self.assertTrue(d["human_review_required"])
        self.assertTrue(d["ai_disclosure"])
        self.assertIsNone(d["recipient"])
        with self.assertRaises(ValueError):
            draft_question(courier_id=24, source_id="arxiv-ai", question="Hi")

    def test_dashboard_serves_mobile_ui_without_external_scripts(self):
        page = self.client.get("/limbo-external")
        self.assertEqual(page.status_code, 200)
        self.assertIn('lang="fi"', page.text)
        self.assertIn('id="agents"', page.text)
        self.assertIn('id="preview"', page.text)
        self.assertIn('id="draft-form"', page.text)
        self.assertIn('connect-src \'self\'', page.text)
        for name in ("limbo-external-view.js", "limbo-external.css"):
            result = self.client.get("/static/" + name)
            self.assertEqual(result.status_code, 200)
        js = self.client.get("/static/limbo-external-view.js").text
        self.assertIn('"/api/limbo-external/preview"', js)
        self.assertIn('"/api/limbo-external/question-draft"', js)
        self.assertIn('textContent', js)
        self.assertNotIn("innerHTML", js)
        self.assertNotIn('fetch("https:', js)

    def test_api_reads_catalog_without_network_or_memory_permission(self):
        response = self.client.get("/api/limbo-external/agents")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["agents"]), 8)
        self.assertFalse(response.json()["external_actions"])
        self.assertFalse(response.json()["memory_write_enabled"])
        s = self.client.get("/api/limbo-external/sources")
        self.assertEqual(s.status_code, 200)
        self.assertFalse(s.json()["network_fetch_from_api"])
        self.assertEqual(len(s.json()["sources"]), 8)

    def test_api_preview_strict_and_unsent_draft(self):
        endpoint = "/api/limbo-external/preview"
        valid = sample()
        response = self.client.post(endpoint, json={"documents": [valid]})
        self.assertEqual(response.status_code, 200, response.text[:400])
        self.assertEqual(response.json()["receipts"][0]["publisher_group"], "arxiv")
        for changes in (
            {"url": "http://arxiv.org/abs/123"},
            {"courier_id": 24},
            {"source_id": "fake"},
            {"classification": "restricted"},
        ):
            with self.subTest(changes=changes):
                denied = self.client.post(endpoint, json={"documents": [{**valid, **changes}]})
                self.assertEqual(denied.status_code, 422)
        draft = self.client.post("/api/limbo-external/question-draft", json={
            "source_id": "arxiv-ai", "courier_id": 55, "question": "Miten aineisto kerättiin?"})
        self.assertEqual(draft.status_code, 200)
        self.assertFalse(draft.json()["publish_action"])

    def test_weekend_empty_rss_has_clear_next_step(self):
        feed = b"""<rss version="2.0"><channel><title>cs.AI</title>
        <skipDays><day>Saturday</day><day>Sunday</day></skipDays>
        </channel></rss>"""
        self.assertEqual(parse_feed("arxiv-ai", feed), [])
        with patch("klone.limbo_external.fetch_source", return_value=[]):
            with self.assertRaises(SystemExit) as cm:
                main(["--fetch", "--source", "arxiv-ai",
                      "--output", "/tmp/missing-weekend-report.json"])
        self.assertIn("--recent", str(cm.exception))
        self.assertIn("Saturday/Sunday", str(cm.exception))

    def test_recent_arxiv_api_atom_accepts_only_canonical_article_links(self):
        atom = b"""<feed xmlns="http://www.w3.org/2005/Atom">
          <entry><id>http://arxiv.org/abs/2601.12345v1</id>
          <title>A verified syntax fixture</title>
          <link href="http://arxiv.org/abs/2601.12345v1" rel="alternate"/>
          <summary>Original API summaries may be very long</summary>
          <updated>2026-11-13T09:00:00Z</updated></entry>
          <entry><title>Off-site</title><link href="http://localhost/private"/>
          <summary>unsafe</summary></entry>
          </feed>"""
        rows = parse_feed("arxiv-ai", atom)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["url"], "https://arxiv.org/abs/2601.12345v1")
        self.assertEqual(rows[0]["courier_id"], 55)
        with self.assertRaises(ValueError):
            validate_documents([{**rows[0], "url": "http://arxiv.org/abs/2601.12345v1"}])
        self.assertEqual(parse_feed("smithsonian-arts", atom), [])

    def test_recent_api_has_no_user_selected_target_and_bounds_results(self):
        url = ("https://export.arxiv.org/api/query?" + urlencode({
            "search_query": "cat:cs.AI", "start": 0, "max_results": 6,
            "sortBy": "submittedDate", "sortOrder": "descending",
        }))
        body = ("""<feed xmlns="http://www.w3.org/2005/Atom">
          <entry><title>Recent article</title><link rel="alternate"
          href="https://arxiv.org/abs/2601.12345"/>
          <summary>Recent summary</summary></entry></feed>""").encode()
        reply = MagicMock()
        reply.__enter__.return_value = reply
        reply.status = 200
        reply.url = url
        reply.headers = {"Content-Type": "application/atom+xml"}
        reply.read.return_value = body
        opener = MagicMock()
        opener.open.return_value = reply
        with patch("klone.limbo_external.build_opener", return_value=opener):
            rows = fetch_recent_arxiv("arxiv-ai")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "Recent article")
        req = opener.open.call_args.args[0]
        self.assertEqual(req.full_url, url)
        self.assertEqual(opener.open.call_args.kwargs["timeout"], 12.0)
        with self.assertRaises(ValueError):
            fetch_recent_arxiv("bbc-world")
        with self.assertRaises(ValueError):
            fetch_recent_arxiv("https://169.254.169.254/latest/meta-data")

    def test_recent_cli_opt_in_and_no_writes_without_data(self):
        with self.assertRaises(SystemExit):
            main(["--recent", "--source", "arxiv-ai",
                  "--output", "/tmp/missing-optin.json"])
        with patch("klone.limbo_external.fetch_recent_arxiv", return_value=[sample()]) as f, \
                patch("klone.limbo_external.write_new_report") as writer:
            self.assertEqual(main(["--fetch", "--recent", "--source", "arxiv-ai",
                                   "--output", "/tmp/just-mocked.json"]), 0)
            f.assert_called_once_with("arxiv-ai")
            writer.assert_called_once()
            report = json.loads(writer.call_args.args[1])
            self.assertEqual(report["fetch_kind"], "explicit_arxiv_recent_api")
            self.assertEqual(len(report["receipts"]), 1)
            self.assertFalse(report["facts_are_verified"])
        with patch("klone.limbo_external.fetch_recent_arxiv", side_effect=ValueError("HTTP 503")), \
                patch("klone.limbo_external.write_new_report") as writer:
            with self.assertRaises(SystemExit) as cm:
                main(["--fetch", "--recent", "--source", "arxiv-ai",
                      "--output", "/tmp/no-mocked.json"])
            writer.assert_not_called()
            self.assertIn("HTTP 503", str(cm.exception))

    def test_manual_fetch_is_only_from_allowlisted_id_and_no_automatic_fetch(self):
        with self.assertRaises(ValueError):
            fetch_source("https://169.254.169.254/latest/meta-data")
        with patch("klone.limbo_external.fetch_source") as fake_fetch:
            self.client.get("/api/limbo-external/agents")
            self.client.get("/api/limbo-external/sources")
            self.client.post("/api/limbo-external/preview", json={"documents": [sample()]})
            fake_fetch.assert_not_called()
        with self.assertRaises(SystemExit):
            main(["--output", "/tmp/no-output-created.json"])


if __name__ == "__main__":
    unittest.main()
