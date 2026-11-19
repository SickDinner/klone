"""KLONE Knowledge Atlas: public Wikipedia corpus, strictly separate from Memory Core.

SQLite + FTS5 when available; Wikitext dumps are indexed as WIKITEXT,
not incorrectly represented as verified plain text. Uses only public
Wikipedia sources with revision/permalink/attribution, bounded per-page
payload, disk quotas, an explicit network gate, and no GPT/tool authority.
"""
from __future__ import annotations

import argparse
import bz2
from contextlib import closing
from datetime import datetime, timezone
import gzip
import hmac
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import re
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zlib

from .council72 import catalog
from .evidence_io import checked_path
from .knowledge_atlas_topics import (
    LANGUAGES, PHASES, ROLE_TOPICS, SHARED_FOUNDATIONS,
    TARGET_UNIQUE_ARTICLES, discovery_seeds, plan, profiles,
)

ATLAS_KIND = "klone-wikimedia-knowledge-atlas-v1"
LICENSE = "CC BY-SA 4.0 (Wikipedia text; verify article exceptions)"
LICENSE_URL = "https://creativecommons.org/licenses/by-sa/4.0/"
CONTACT = "https://github.com/SickDinner/klone"
MAX_TEXT_CHARS = 12_000
MAX_RESULT_CHARS = 450
MAX_ARTICLES_HARD = 100_000
MAX_REQUESTS_PER_RUN = 12
MAX_PAGES_PER_API_REQUEST = 20
DEFAULT_MAX_MB = 512
VALID_TOKEN = re.compile(r"(?u)[^\W_]{2,}", re.UNICODE)
PAGE_FORMATS = ("api_plaintext_extract", "dump_wikitext")
MAX_PAGE_BYTES = 160_000


class AtlasError(ValueError):
    pass


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha(raw: str) -> str:
    return sha256(raw.encode("utf-8")).hexdigest()


def _project_url(language: str) -> str:
    if language not in LANGUAGES:
        raise AtlasError("Wikipedia language is not allowlisted")
    return f"https://{language}.wikipedia.org"


def _page_attribution(language: str, page_id: int, rev_id: int,
                      title: str) -> dict:
    host = _project_url(language)
    return {
        "revision_permalink": f"{host}/w/index.php?oldid={rev_id}",
        "contributors_history": (
            f"{host}/w/index.php?title="
            + urllib.parse.quote(title.replace(" ", "_"), safe="")
            + "&action=history"
        ),
        "license_name": LICENSE,
        "license_url": LICENSE_URL,
    }


def _check_positive_int(value, maximum, name):
    if type(value) is not int or not 1 <= value <= maximum:
        raise AtlasError(f"{name} must be within 1..{maximum}")


def _prepared_article(language, page_id, title, revision_id, revision_at,
                      content, content_kind):
    _project_url(language)
    _check_positive_int(page_id, 2_147_483_647, "page ID")
    _check_positive_int(revision_id, 2_147_483_647, "revision ID")
    if content_kind not in PAGE_FORMATS:
        raise AtlasError("unknown article content format")
    if type(title) is not str or not 1 <= len(title.strip()) <= 300:
        raise AtlasError("invalid Wikipedia title")
    if any(ord(ch) < 32 for ch in title):
        raise AtlasError("control character in title")
    if type(content) is not str or not content.strip():
        raise AtlasError("empty article content")
    if type(revision_at) is not str or not re.fullmatch(
            r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", revision_at):
        raise AtlasError("invalid revision timestamp")
    original_bytes = len(content.encode("utf-8"))
    if original_bytes > 12_000_000:
        raise AtlasError("oversized source page: excluded")
    clipped = content[:MAX_TEXT_CHARS]
    record = {
        "language": language, "page_id": page_id,
        "title": title.strip(), "revision_id": revision_id,
        "revision_at": revision_at,
        "content": clipped, "content_kind": content_kind,
        "truncated": len(content) > len(clipped),
        "original_length_chars": len(content),
        "original_sha256": _sha(content),
        "stored_sha256": _sha(clipped),
        "original_bytes": original_bytes,
    }
    record.update(_page_attribution(language, page_id, revision_id,
                                    record["title"]))
    return record


def _fts_tokens(query):
    if type(query) is not str or not 2 <= len(query.strip()) <= 250:
        raise AtlasError("search query must be 2..250 characters")
    words = VALID_TOKEN.findall(query.casefold())[:12]
    if not words:
        raise AtlasError("search query has no indexable terms")
    # Quoted FTS tokens avoid SQL injection, MATCH operators and wildcards.
    # Require all question terms: Wikipedia evidence should not be diluted
    # by articles matching only common words ("scientific" OR "method").
    return " AND ".join('"' + w.replace('"', '') + '"' for w in words)


def _safe_root(root: Path):
    root = Path(root).expanduser().absolute()
    checked_path(root)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    checked_path(root, directory=True)
    return root


class Atlas:
    def __init__(self, root: Path, *, max_mb: int = DEFAULT_MAX_MB):
        _check_positive_int(max_mb, 8192, "disk limit MB")
        self.root = _safe_root(root)
        self.path = checked_path(self.root / "wikipedia.sqlite3")
        self.max_bytes = max_mb * 1024 * 1024
        self.db = sqlite3.connect(str(self.path), timeout=20)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA busy_timeout=20000")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY,
                language TEXT NOT NULL,
                page_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                revision_id INTEGER NOT NULL,
                revision_at TEXT NOT NULL,
                revision_permalink TEXT NOT NULL,
                contributors_history TEXT NOT NULL,
                license_name TEXT NOT NULL,
                license_url TEXT NOT NULL,
                content_kind TEXT NOT NULL,
                body_zip BLOB NOT NULL,
                truncated INTEGER NOT NULL CHECK(truncated IN (0,1)),
                original_length_chars INTEGER NOT NULL,
                original_sha256 TEXT NOT NULL,
                stored_sha256 TEXT NOT NULL,
                acquired_at TEXT NOT NULL,
                ingestion_kind TEXT NOT NULL,
                public_unverified INTEGER NOT NULL DEFAULT 1,
                UNIQUE(language, page_id)
            );
            CREATE INDEX IF NOT EXISTS idx_articles_language
                ON articles(language, title);
            CREATE TABLE IF NOT EXISTS role_articles(
                member_id INTEGER NOT NULL,
                article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
                provenance_reason TEXT NOT NULL CHECK(
                    provenance_reason IN ('api_topic_seed','lexical_topic_hint')
                ),
                PRIMARY KEY(member_id, article_id)
            );
            CREATE INDEX IF NOT EXISTS idx_role_articles_article
                ON role_articles(article_id);
            CREATE TABLE IF NOT EXISTS progress(
                name TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
        self.fts_enabled = True
        try:
            self.db.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS article_fts
                USING fts5(title, body, tokenize='unicode61 remove_diacritics 2')
            """)
        except sqlite3.OperationalError as exc:
            if "fts5" not in str(exc).lower():
                raise
            self.fts_enabled = False
        self.db.commit()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.db.close()

    def disk_bytes(self):
        return sum(
            p.stat().st_size for p in (
                self.path, Path(str(self.path) + "-wal"),
                Path(str(self.path) + "-shm")
            ) if p.exists()
        )

    def current_count(self) -> int:
        return self.db.execute("SELECT count(*) FROM articles").fetchone()[0]

    def _possible_lexical_roles(self, title, body):
        # A weak, disclosed matching heuristic; never proof of expertise.
        searchable = (title + "\n" + body[:900]).casefold()
        hits = []
        for member_id, terms in ROLE_TOPICS.items():
            overlap = sum(1 for term in terms if term.casefold() in searchable)
            if overlap:
                hits.append((member_id, overlap))
        hits.sort(key=lambda x: (-x[1], x[0]))
        return [member_id for member_id, _ in hits[:6]]

    def ingest(self, record: dict, *, reason="lexical_topic_hint",
               seed_member=None) -> str:
        if type(record) is not dict:
            raise AtlasError("expected validated article dictionary")
        article = _prepared_article(**record)
        with self.db:
            row = self.db.execute(
                "SELECT id, revision_id, revision_at FROM articles "
                "WHERE language=? AND page_id=?",
                (article["language"], article["page_id"])
            ).fetchone()
            is_new = row is None
            if is_new and self.current_count() >= MAX_ARTICLES_HARD:
                raise AtlasError("hard cap on distinct articles reached")
            if (row is None or article["revision_id"] != row["revision_id"]) and (
                self.disk_bytes() + len(article["content"].encode("utf-8")) * 4
                > self.max_bytes
            ):
                raise AtlasError("atlas disk budget exceeded; no additional page stored")
            if row is not None and article["revision_id"] == row["revision_id"]:
                status = "unchanged"
                article_id = row["id"]
            elif row is not None and article["revision_at"] < row["revision_at"]:
                status = "older_skipped"
                article_id = row["id"]
            else:
                packed = zlib.compress(article["content"].encode("utf-8"), level=6)
                self.db.execute("""
                    INSERT INTO articles (
                        language,page_id,title,revision_id,revision_at,
                        revision_permalink,contributors_history,license_name,
                        license_url,content_kind,body_zip,truncated,
                        original_length_chars,original_sha256,stored_sha256,
                        acquired_at,ingestion_kind
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(language,page_id) DO UPDATE SET
                        title=excluded.title,revision_id=excluded.revision_id,
                        revision_at=excluded.revision_at,
                        revision_permalink=excluded.revision_permalink,
                        contributors_history=excluded.contributors_history,
                        license_name=excluded.license_name,
                        license_url=excluded.license_url,
                        content_kind=excluded.content_kind,
                        body_zip=excluded.body_zip,
                        truncated=excluded.truncated,
                        original_length_chars=excluded.original_length_chars,
                        original_sha256=excluded.original_sha256,
                        stored_sha256=excluded.stored_sha256,
                        acquired_at=excluded.acquired_at,
                        ingestion_kind=excluded.ingestion_kind
                """, (
                    article["language"], article["page_id"], article["title"],
                    article["revision_id"], article["revision_at"],
                    article["revision_permalink"], article["contributors_history"],
                    article["license_name"], article["license_url"],
                    article["content_kind"], sqlite3.Binary(packed),
                    int(article["truncated"]), article["original_length_chars"],
                    article["original_sha256"], article["stored_sha256"], _utc(),
                    article["content_kind"]
                ))
                article_id = self.db.execute(
                    "SELECT id FROM articles WHERE language=? AND page_id=?",
                    (article["language"], article["page_id"])
                ).fetchone()[0]
                if self.fts_enabled:
                    self.db.execute("DELETE FROM article_fts WHERE rowid=?",
                                    (article_id,))
                    self.db.execute(
                        "INSERT INTO article_fts(rowid,title,body) VALUES(?,?,?)",
                        (article_id, article["title"], article["content"])
                    )
                status = "inserted" if is_new else "updated"
            if seed_member is not None:
                _check_positive_int(seed_member, 72, "member ID")
                if seed_member not in ROLE_TOPICS:
                    raise AtlasError("non-canonical member ID")
                self.db.execute("""
                    INSERT INTO role_articles(member_id,article_id,provenance_reason)
                    VALUES (?,?,?) ON CONFLICT(member_id,article_id) DO NOTHING
                """, (seed_member, article_id, "api_topic_seed"))
            elif status in ("inserted", "updated"):
                for member_id in self._possible_lexical_roles(
                        article["title"], article["content"]):
                    self.db.execute("""
                        INSERT INTO role_articles(member_id,article_id,provenance_reason)
                        VALUES (?,?,?) ON CONFLICT(member_id,article_id) DO NOTHING
                    """, (member_id, article_id, "lexical_topic_hint"))
        return status

    def state(self):
        count = self.current_count()
        languages = dict(self.db.execute(
            "SELECT language,count(*) FROM articles GROUP BY language"
        ).fetchall())
        roles = self.db.execute(
            "SELECT count(DISTINCT member_id) FROM role_articles"
        ).fetchone()[0]
        indexed = self.db.execute("SELECT count(*) FROM role_articles").fetchone()[0]
        return {
            "kind": ATLAS_KIND,
            "distinct_article_count": count,
            "articles_by_language": languages,
            "indexed_member_coverage": roles,
            "member_article_links": indexed,
            "target_distinct_articles": TARGET_UNIQUE_ARTICLES,
            "phase_goals": list(PHASES),
            "remaining_to_target": max(0, TARGET_UNIQUE_ARTICLES-count),
            "storage_bytes_current": self.disk_bytes(),
            "storage_bytes_soft_limit": self.max_bytes,
            "fts5_available": self.fts_enabled,
            "text_character_cap_per_article": MAX_TEXT_CHARS,
            "public_corpus_separate_from_main_memory": True,
            "autonomous_authority": False,
            "memory_write": False,
            "scientific_truth_verified": False,
            "license_attribution_required": True,
        }

    def member_coverage(self):
        """72 deterministic specialist coverage stats; counts are not skills."""
        counts = {
            member_id: (total, api_count, hint_count)
            for member_id, total, api_count, hint_count
            in self.db.execute("""
                SELECT member_id,COUNT(*),
                       SUM(CASE WHEN provenance_reason='api_topic_seed'
                                THEN 1 ELSE 0 END),
                       SUM(CASE WHEN provenance_reason='lexical_topic_hint'
                                THEN 1 ELSE 0 END)
                FROM role_articles GROUP BY member_id
            """)
        }
        members = []
        for role in profiles():
            member_id = role["member_id"]
            total, api, hint = counts.get(member_id, (0, 0, 0))
            members.append({
                "member_id": member_id,
                "ring_id": role["ring_id"],
                "name": role["name"],
                "task": role["canonical_task"],
                "expertise_topics": role["expertise_topics"],
                "linked_public_pages": total,
                "pages_from_explicit_role_queries": api,
                "pages_from_weak_keyword_hints": hint,
                "expertise_established_by_count": False,
            })
        return {
            "kind": "klone-atlas-72-coverage-v1",
            "unique_articles": self.current_count(),
            "member_profiles": members,
            "members_with_any_article": sum(
                1 for m in members if m["linked_public_pages"] > 0
            ),
            "members_without_article_links": [
                m["member_id"] for m in members
                if not m["linked_public_pages"]
            ],
            "retrieval_index_not_scientific_verification": True,
            "model_api_requests": 0,
            "memory_write": False,
        }

    def search(self, question: str, *, member_id: int | None = None,
               language: str | None = None, limit=8):
        _check_positive_int(limit, 30, "search limit")
        if member_id is not None:
            _check_positive_int(member_id, 72, "member ID")
        if language is not None:
            _project_url(language)
        tokens = _fts_tokens(question)
        params = []
        role_sql = ("LEFT JOIN role_articles ra ON ra.article_id=a.id "
                    "AND ra.member_id=? " if member_id is not None else "")
        if member_id is not None:
            params.append(member_id)
        if self.fts_enabled:
            sql = ("SELECT a.*, " +
                   ("CASE WHEN ra.member_id IS NULL THEN 0 ELSE 1 END AS specialist_hit, "
                    if member_id is not None else "0 AS specialist_hit, ") +
                   "bm25(article_fts,3.0,1.0) AS rank "
                   "FROM article_fts JOIN articles a ON a.id=article_fts.rowid " +
                   role_sql + "WHERE article_fts MATCH ? ")
            params.append(tokens)
        else:
            terms = VALID_TOKEN.findall(question.casefold())[:5]
            sql = ("SELECT a.*, " +
                   ("CASE WHEN ra.member_id IS NULL THEN 0 ELSE 1 END AS specialist_hit, "
                    if member_id is not None else "0 AS specialist_hit, ") +
                   "0 AS rank FROM articles a " + role_sql +
                   "WHERE (" + " OR ".join(
                       "a.title LIKE ? OR CAST(a.body_zip AS TEXT) LIKE ?"
                       for _ in terms
                   ) + ") ")
            # Without FTS, fallback only reliably searches TITLES, not compressed bodies.
            sql = sql.replace(" OR CAST(a.body_zip AS TEXT) LIKE ?", "")
            sql = sql.replace(" OR a.title LIKE ?", " AND a.title LIKE ?")
            params.extend("%" + word + "%" for word in terms)
        if language is not None:
            sql += "AND a.language=? "
            params.append(language)
        sql += ("ORDER BY specialist_hit DESC, rank, a.language, a.page_id "
                "LIMIT ?")
        params.append(limit)
        results = []
        for row in self.db.execute(sql, params).fetchall():
            text = zlib.decompress(row["body_zip"]).decode("utf-8")
            if _sha(text) != row["stored_sha256"]:
                raise AtlasError("article content integrity mismatch")
            results.append({
                "language": row["language"], "page_id": row["page_id"],
                "revision_id": row["revision_id"],
                "title": row["title"],
                "source_version_timestamp": row["revision_at"],
                "source_url": row["revision_permalink"],
                "attribution_url": row["contributors_history"],
                "license_name": row["license_name"],
                "license_url": row["license_url"],
                "content_kind": row["content_kind"],
                "text_excerpt_untrusted": text[:MAX_RESULT_CHARS],
                "stored_sha256": row["stored_sha256"],
                "truncated": bool(row["truncated"]),
                "specialist_seed_or_topic_hit": bool(row["specialist_hit"]),
                "source_truth_verified": False,
            })
        return {
            "kind": "klone-atlas-public-search-v1",
            "query": question,
            "requested_member_id": member_id,
            "member_specialty": list(ROLE_TOPICS[member_id])
                if member_id is not None else None,
            "matched_sources": results,
            "source_count": len(results),
            "retrieval_only_no_model_call": True,
            "source_truth_verified": False,
            "memory_write": False,
        }

    def get_cursor(self, language):
        row = self.db.execute(
            "SELECT value FROM progress WHERE name=?",
            ("api_cursor:" + language,)
        ).fetchone()
        return int(row[0]) if row else 0

    def save_cursor(self, language, n):
        with self.db:
            self.db.execute("""
                INSERT INTO progress(name,value) VALUES (?,?)
                ON CONFLICT(name) DO UPDATE SET value=excluded.value
            """, ("api_cursor:" + language, str(n)))


def _api_pages(payload, language):
    if type(payload) is not dict or "error" in payload:
        raise AtlasError("Wikimedia API returned an error or invalid JSON")
    query = payload.get("query", {})
    pages = query.get("pages", [])
    if type(pages) is not list:
        raise AtlasError("unexpected MediaWiki pages format")
    result = []
    for p in pages:
        if type(p) is not dict or p.get("ns") != 0 or p.get("missing"):
            continue
        revs = p.get("revisions") or []
        if (not isinstance(revs, list) or not revs or
                type(revs[0]) is not dict):
            continue
        if not p.get("extract", "").strip():
            continue
        r = revs[0]
        try:
            article = _prepared_article(
                language, p["pageid"], p["title"],
                r["revid"], r["timestamp"], p["extract"],
                "api_plaintext_extract",
            )
        except (KeyError, AtlasError):
            continue
        result.append(article)
    return result


def _mediawiki_request(language: str, query: str, *, user_agent: str,
                       timeout=25):
    if (type(user_agent) is not str or not 15 <= len(user_agent) <= 250 or
            not ("https://" in user_agent or "@" in user_agent)):
        raise AtlasError("a descriptive, contactable Wikimedia User-Agent is required")
    url = _project_url(language) + "/w/api.php?" + urllib.parse.urlencode({
        "action": "query", "format": "json", "formatversion": "2",
        "generator": "search", "gsrsearch": query,
        "gsrnamespace": "0", "gsrlimit": str(MAX_PAGES_PER_API_REQUEST),
        "prop": "extracts|revisions", "explaintext": "1",
        "exchars": "9000", "exlimit": "max",
        "rvprop": "ids|timestamp", "rvlimit": "1",
        "maxlag": "5",
    })
    req = urllib.request.Request(url, headers={
        "User-Agent": user_agent, "Accept": "application/json"
    })
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, request, fp, code, msg, headers, newurl):
            raise AtlasError("unexpected Wikimedia redirect refused")
    opener = urllib.request.build_opener(NoRedirect())
    try:
        with opener.open(req, timeout=timeout) as res:
            if res.status != 200:
                raise AtlasError("Wikipedia API response not HTTP 200")
            data = res.read(1_200_001)
    except urllib.error.HTTPError as exc:
        if exc.code in (429, 503):
            raise AtlasError("Wikimedia is rate-limiting or busy; stop and retry later") from None
        raise AtlasError(f"Wikimedia HTTP {exc.code}: stopped, no retry") from None
    except (urllib.error.URLError, TimeoutError):
        raise AtlasError("Wikimedia endpoint unreachable; no automatic retry") from None
    if len(data) > 1_200_000:
        raise AtlasError("Wikimedia response exceeded size limit")
    try:
        return json.loads(data)
    except (ValueError, UnicodeError):
        raise AtlasError("Wikimedia JSON parse failed") from None


def collect(atlas: Atlas, *, language: str, requests: int,
            user_agent: str, delay: float = 2.0, sender=None):
    """Explicit bounded network ingestion. 72*3 deterministic seed queries.

    This small-calls pathway is for initial demonstrations and gap filling;
    large scale must use official monthly dump imports, NOT rate-limit evasion.
    """
    _project_url(language)
    _check_positive_int(requests, MAX_REQUESTS_PER_RUN, "network request count")
    if not 1.5 <= delay <= 60:
        raise AtlasError("polite delay must be at least 1.5 seconds")
    if sender is None:
        sender = _mediawiki_request
    seeds = discovery_seeds(language)
    start = atlas.get_cursor(language)
    outcomes = {"api_requests": 0, "articles_inserted": 0,
                "articles_updated": 0, "articles_unchanged": 0,
                "source_queries": [], "source_language": language}
    for i in range(requests):
        ix = (start + i) % len(seeds)
        member_id, topic = seeds[ix]
        payload = sender(language, topic, user_agent=user_agent)
        outcomes["api_requests"] += 1
        articles = _api_pages(payload, language)
        for record in articles:
            status = atlas.ingest({
                k: record[k] for k in (
                    "language", "page_id", "title", "revision_id",
                    "revision_at", "content", "content_kind",
                )
            }, seed_member=member_id)
            outcomes["articles_" + (
                "inserted" if status == "inserted" else
                "updated" if status == "updated" else "unchanged"
            )] += 1
        atlas.save_cursor(language, (ix + 1) % len(seeds))
        outcomes["source_queries"].append({
            "member_id": member_id, "topic": topic,
            "seed_kind": "shared_foundation" if member_id is None else "specialist",
            "articles_returned": len(articles)
        })
        if i < requests - 1:
            time.sleep(delay)
    return outcomes


def _xml_tag(element):
    return element.tag.rsplit("}", 1)[-1]


def _parse_xml_page(page, language):
    if page.find("{*}redirect") is not None:
        return None
    try:
        ns = page.findtext("{*}ns")
        if ns != "0":
            return None
        rev = page.find("{*}revision")
        if rev is None:
            return None
        body_node = rev.find(".//{*}text")
        if body_node is None or not body_node.text:
            return None
        return {
            "language": language,
            "page_id": int(page.findtext("{*}id")),
            "title": page.findtext("{*}title"),
            "revision_id": int(rev.findtext("{*}id")),
            "revision_at": rev.findtext("{*}timestamp"),
            "content": body_node.text,
            "content_kind": "dump_wikitext",
        }
    except (TypeError, ValueError, AttributeError):
        return None


def import_local_dump(atlas, filepath: Path, *, language: str,
                      max_pages: int = 500, skip_pages: int = 0,
                      expected_sha256: str | None = None):
    _project_url(language)
    _check_positive_int(max_pages, 20_000, "dump import page count")
    if type(skip_pages) is not int or not 0 <= skip_pages <= 50_000_000:
        raise AtlasError("invalid dump resume offset")
    path = checked_path(Path(filepath).expanduser().absolute())
    if not path.is_file() or path.suffix not in (".xml", ".bz2", ".gz"):
        raise AtlasError("require local Wikimedia XML, XML.bz2 or XML.gz")
    verified_digest = None
    if expected_sha256 is not None:
        if type(expected_sha256) is not str or not re.fullmatch(
                "[0-9a-fA-F]{64}", expected_sha256):
            raise AtlasError("expected SHA256 must contain exactly 64 hex characters")
        digest = sha256()
        with open(path, "rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        verified_digest = digest.hexdigest()
        if not hmac.compare_digest(
                verified_digest, expected_sha256.lower()):
            raise AtlasError("dump SHA256 mismatch; refusing import")
    opener = bz2.open if path.suffix == ".bz2" else (
        gzip.open if path.suffix == ".gz" else open
    )
    stats = {"scanned_main_namespace_non_redirect": 0,
             "skipped_at_start": skip_pages,
             "articles_inserted": 0, "articles_updated": 0,
             "articles_unchanged": 0, "excluded_large_or_invalid": 0,
             "input_filename": path.name,
             "input_file_sha256_verified": verified_digest is not None,
             "input_file_sha256": verified_digest,
             "source_format": "raw XML wikitext, not plaintext",
             "stopped_at_scan_offset": skip_pages}
    with opener(path, "rb") as handle:
        header = handle.peek(4096)[:4096] if hasattr(handle, "peek") else b""
        if b"<!DOCTYPE" in header or b"<!ENTITY" in header:
            raise AtlasError("DOCTYPE or XML entity definitions not allowed")
        root = None
        for event, item in ET.iterparse(handle, events=("start", "end")):
            if root is None and event == "start":
                root = item
            if event != "end" or _xml_tag(item) != "page":
                continue
            candidate = _parse_xml_page(item, language)
            if candidate is not None:
                stats["scanned_main_namespace_non_redirect"] += 1
                scanned = stats["scanned_main_namespace_non_redirect"]
                if scanned > skip_pages:
                    try:
                        status = atlas.ingest(candidate)
                    except AtlasError as exc:
                        if "oversized" in str(exc) or "empty" in str(exc):
                            stats["excluded_large_or_invalid"] += 1
                        else:
                            raise
                    else:
                        stats["articles_" + (
                            "inserted" if status == "inserted" else
                            "updated" if status == "updated" else "unchanged"
                        )] += 1
                    stats["stopped_at_scan_offset"] = scanned
            item.clear()
            if root is not None:
                root.clear()
            if stats["stopped_at_scan_offset"] >= skip_pages + max_pages:
                break
    return stats


def _json_out(data):
    print(json.dumps(data, ensure_ascii=False, indent=2,
                     sort_keys=True, allow_nan=False))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Local-first Wikipedia Knowledge Atlas (public, read-only to KLONE)"
    )
    parser.add_argument("--root", type=Path,
                        default=Path.home() / "klone-var/knowledge-atlas")
    parser.add_argument("--max-mb", type=int, default=DEFAULT_MAX_MB)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("plan")
    sub.add_parser("status")
    sub.add_parser("coverage")
    look = sub.add_parser("search")
    look.add_argument("query")
    look.add_argument("--member-id", type=int)
    look.add_argument("--language", choices=LANGUAGES)
    look.add_argument("--limit", type=int, default=8)
    member = sub.add_parser("member")
    member.add_argument("member_id", type=int)
    c = sub.add_parser("collect")
    c.add_argument("--allow-network", action="store_true")
    c.add_argument("--language", choices=LANGUAGES, default="fi")
    c.add_argument("--requests", type=int, default=2)
    c.add_argument("--delay", type=float, default=2.0)
    c.add_argument("--contact", default=CONTACT)
    d = sub.add_parser("import-dump")
    d.add_argument("--input", type=Path, required=True)
    d.add_argument("--language", choices=LANGUAGES, required=True)
    d.add_argument("--max-pages", type=int, default=500)
    d.add_argument("--skip-pages", type=int, default=0)
    d.add_argument("--expected-sha256")
    args = parser.parse_args(argv)
    try:
        if args.command == "plan":
            return _json_out(plan())
        with Atlas(args.root, max_mb=args.max_mb) as atlas:
            if args.command == "status":
                output = atlas.state()
            elif args.command == "coverage":
                output = atlas.member_coverage()
            elif args.command == "search":
                output = atlas.search(
                    args.query, member_id=args.member_id,
                    language=args.language, limit=args.limit
                )
            elif args.command == "member":
                output = next((p for p in profiles()
                               if p["member_id"] == args.member_id), None)
                if output is None:
                    raise AtlasError("non-canonical Council72 member")
            elif args.command == "collect":
                if not args.allow_network:
                    raise PermissionError(
                        "network ingestion requires --allow-network"
                    )
                ua = (f"KLONE-KnowledgeAtlas/0.1 ({args.contact}; "
                      "public Wikipedia research)")
                output = collect(
                    atlas, language=args.language, requests=args.requests,
                    user_agent=ua, delay=args.delay
                )
                output["atlas_after"] = atlas.state()
            else:
                output = import_local_dump(
                    atlas, args.input, language=args.language,
                    max_pages=args.max_pages, skip_pages=args.skip_pages,
                    expected_sha256=args.expected_sha256
                )
                output["atlas_after"] = atlas.state()
        return _json_out(output)
    except (AtlasError, PermissionError, OSError, sqlite3.Error,
            ET.ParseError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
