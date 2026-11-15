"""Limbo External Intelligence Network, phase E1: public-feed research and drafts.

Eight existing council couriers receive bounded public RSS/Atom observations.
No automated posting, arbitrary URL fetch, private data access, or model egress.
Fetched claims remain *unverified* in the existing Council 72 session contract.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
from html import unescape
import json
import re
import ssl
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener, HTTPSHandler
import xml.etree.ElementTree as ET

from .council72 import catalog
from .council72_session import run_session
from .cognition_experiment_lab import neurochemical_policy
from .evidence_io import write_new_report

MAX_BYTES = 1024 * 1024
MAX_DOCUMENTS = 48
MAX_FEED_ITEMS = 6
USER_AGENT = "KLONE-LimboPublicResearch/0.1 (research feed reader; no publishing)"
ATOM_NS = "{http://www.w3.org/2005/Atom}"
TAGS = re.compile(r"<[^>]{0,4000}>")
SPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class PublicFeed:
    id: str
    courier_id: int
    topic: str
    url: str
    publisher_group: str
    allowed_article_hosts: tuple[str, ...]
    source_note: str


# Exact, operator-reviewable public feeds; never constructed from user input.
# Each courier has one starting source; the fixed set is intentionally small.
FEEDS = (
    PublicFeed("bbc-world", 24, "Kielten ja yleisöjen ymmärtäminen",
               "https://feeds.bbci.co.uk/news/world/rss.xml", "bbc",
               ("www.bbc.com", "www.bbc.co.uk", "bbc.com", "bbc.co.uk"),
               "World reporting is one publisher, not multiple independent witnesses."),
    PublicFeed("bbc-science", 27, "Yhteiskunnan tiedekeskustelu",
               "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml", "bbc",
               ("www.bbc.com", "www.bbc.co.uk", "bbc.com", "bbc.co.uk"),
               "BBC World and Science share a publisher and a source group."),
    PublicFeed("nasa-technology", 30, "Teknologinen dokumentaatio",
               "https://www.nasa.gov/feed/", "nasa",
               ("www.nasa.gov", "nasa.gov", "science.nasa.gov"),
               "NASA main public feed; verify article topic separately."),
    PublicFeed("smithsonian-innovation", 53, "Yhteisö ja innovaatio",
               "https://www.smithsonianmag.com/rss/innovation/", "smithsonian",
               ("www.smithsonianmag.com", "smithsonianmag.com"),
               "Innovation reporting, not direct community feedback."),
    PublicFeed("arxiv-ai", 55, "Tutkimusväitteiden arviointi",
               "https://rss.arxiv.org/rss/cs.AI", "arxiv",
               ("arxiv.org", "www.arxiv.org", "export.arxiv.org"),
               "Preprints are not necessarily peer reviewed."),
    PublicFeed("nasa-latest", 70, "Ajankohtaiset tutkimushavainnot",
               "https://www.nasa.gov/news-release/feed/", "nasa",
               ("www.nasa.gov", "nasa.gov", "science.nasa.gov"),
               "News releases from NASA, not independent corroboration."),
    PublicFeed("arxiv-neuro", 11, "Neurotieteen kysymysten reititys",
               "https://rss.arxiv.org/rss/q-bio.NC", "arxiv",
               ("arxiv.org", "www.arxiv.org", "export.arxiv.org"),
               "Preprint abstracts provide leads, not proof."),
    PublicFeed("smithsonian-arts", 71, "Kulttuurinen kuvakieli ja keskustelun sävy",
               "https://www.smithsonianmag.com/rss/arts-culture/", "smithsonian",
               ("www.smithsonianmag.com", "smithsonianmag.com"),
               "Cultural editorial coverage from the same Smithsonian publisher."),
)
BY_ID = {s.id: s for s in FEEDS}
BY_COURIER = {s.courier_id: s for s in FEEDS}
assert len(BY_ID) == len(BY_COURIER) == 8


def _sha(value: object) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _clean(text: object, limit: int) -> str:
    if not isinstance(text, str):
        raise ValueError("text must be a string")
    value = SPACE.sub(" ", unescape(TAGS.sub(" ", text))).strip()
    if not value or len(value) > limit or any(ord(c) < 32 for c in value):
        raise ValueError("invalid or oversized text")
    return value


def _public_article_url(url: object, feed: PublicFeed) -> str:
    if not isinstance(url, str) or not 10 <= len(url) <= 256:
        raise ValueError("invalid source URL")
    try:
        parsed = urlsplit(url)
        host = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise ValueError("invalid source URL") from exc
    if (parsed.scheme != "https" or not host or host.lower().rstrip(".") not in feed.allowed_article_hosts
            or parsed.username is not None or parsed.password is not None
            or port not in (None, 443) or parsed.fragment
            or any(ord(c) < 33 for c in url)):
        raise ValueError("source URL must be canonical HTTPS at a source-approved host")
    return url


def agents() -> list[dict]:
    """Reuse the *actual* Council 72 Limbo roster and neurochemical baselines."""
    members = {m["id"]: m for m in catalog()["members"] if m["ring"] == 1}
    if set(members) != set(BY_COURIER):
        raise ValueError("Limbo courier roster no longer matches the public-feed registry")
    output = []
    for feed in FEEDS:
        m = members[feed.courier_id]
        modulators = m["baseline_modulators"]
        output.append({
            "id": m["id"], "name": m["name"], "slot": m["slot"],
            "founder_id": m["courier_for"], "task": m["task"], "topic": feed.topic,
            "feed_id": feed.id, "source_group": feed.publisher_group,
            "baseline_modulators": dict(modulators),
            "attention_preview": neurochemical_policy(
                dopamine=modulators["dopamine"],
                noradrenaline=modulators["noradrenaline"],
                acetylcholine=modulators["acetylcholine"],
                inhibition=modulators["gaba"]),
            "memory_policy": "session_scoped_evidence_only",
            "external_action": False,
            "identity_policy": "pseudonyms_allowed; AI disclosure required for outbound communication",
        })
    return output


def sources() -> list[dict]:
    return [{**asdict(feed),
             "allowed_article_hosts": list(feed.allowed_article_hosts),
             "network_enabled_by_api": False,
             "posting_enabled": False} for feed in FEEDS]


def validate_documents(documents: object) -> list[dict]:
    if not isinstance(documents, list) or not 1 <= len(documents) <= MAX_DOCUMENTS:
        raise ValueError("one to 48 observations required")
    normalized, seen = [], set()
    for raw in documents:
        if not isinstance(raw, dict) or not {"source_id", "courier_id", "url", "title", "summary"} <= raw.keys():
            raise ValueError("observation fields missing")
        if set(raw) - {"source_id", "courier_id", "url", "title", "summary", "published_at"}:
            raise ValueError("unexpected observation field")
        sid = raw["source_id"]
        if not isinstance(sid, str) or sid not in BY_ID:
            raise ValueError("unknown public source ID")
        source = BY_ID[sid]
        if type(raw["courier_id"]) is not int or raw["courier_id"] != source.courier_id:
            raise ValueError("source is bound to another Limbo courier")
        url = _public_article_url(raw["url"], source)
        title, summary = _clean(raw["title"], 240), _clean(raw["summary"], 360)
        pub = raw.get("published_at")
        if pub is not None:
            pub = _clean(pub, 80)
        key = (sid, url)
        if key in seen:
            raise ValueError("duplicate feed observation")
        seen.add(key)
        normalized.append({
            "source_id": sid, "courier_id": source.courier_id, "url": url,
            "title": title, "summary": summary, "published_at": pub,
            "publisher_group": source.publisher_group,
            "receipt_sha256": _sha([sid, url, title, summary, pub]),
            "verification": "publisher_report_not_independently_verified",
        })
    return normalized


def analyze_documents(documents: object, *, goal: str = "Julkisen maailman havaintojen kriittinen tutkiminen") -> dict:
    """Pure deterministic export. No network, memory, publishing or persistence."""
    goal = _clean(goal, 2000)
    records = validate_documents(documents)
    by_id = {a["id"]: a for a in agents()}
    observed = []
    reports = []
    for a in agents():
        own = [x for x in records if x["courier_id"] == a["id"]]
        reports.append({
            "courier_id": a["id"], "name": a["name"],
            "founder_id": a["founder_id"], "observations": len(own),
            "distinct_publisher_groups": len({x["publisher_group"] for x in own}),
            "source_refs": [x["url"] for x in own],
            "epistemic_status": "unverified_reports" if own else "no_evidence",
            "simulated_attention": a["attention_preview"],
        })
    for r in records:
        a = by_id[r["courier_id"]]
        observed.append({
            "id": "web:" + r["receipt_sha256"][:20],
            "courier_id": r["courier_id"],
            "source_ref": r["url"],
            "source_group": r["publisher_group"],
            "claim_key": "lead:" + r["receipt_sha256"][:22],
            "stance": "unknown",
            "summary": (r["title"] + ": " + r["summary"])[:512],
            "classification": "public",
            "signals": {"evidence_quality": 0.15, "uncertainty": 1.0,
                        "risk": 0.25, "novelty": 0.25,
                        "reward": 0.0, "threat": 0.0, "social_feedback": 0.0},
            "observed_at": r["published_at"],
        })
    session_request = {
        "session_id": "external." + _sha([goal, records])[:16],
        "goal": goal, "classification": "public",
        "source_kind": "user_claims",
        "steps": [{"observations": observed[i:i+32]}
                  for i in range(0, len(observed), 32)],
    }
    # Use the existing replayable Council 72 machinery, without authenticating claims.
    session = run_session(session_request)
    return {
        "schema_version": 1, "kind": "klone-limbo-external-preview",
        "source_kind": "public_feed_observation",
        "sources_are_verified": False, "facts_are_verified": False,
        "independent_corroboration": False,
        "authority": {"external_actions": False, "posting": False, "memory_writes": False},
        "input_sha256": _sha(records),
        "receipts": records, "agent_reports": reports,
        "session_request": session_request,
        "session": session,
    }


def draft_question(*, courier_id: int, source_id: str, question: str) -> dict:
    """Generate a *non-sent* transparent question. No destinations or account credentials."""
    if type(courier_id) is not int or courier_id not in BY_COURIER:
        raise ValueError("unknown courier")
    if source_id != BY_COURIER[courier_id].id:
        raise ValueError("source and courier mismatch")
    question = _clean(question, 380)
    agent = next(x for x in agents() if x["id"] == courier_id)
    if question.endswith("?"):
        final_question = question
    else:
        final_question = question + "?"
    return {
        "courier_id": courier_id, "persona": agent["name"],
        "message": f"Hei! Olen automaattinen tutkimusagentti nimimerkillä {agent['name']}. "
                   f"Tarkistan julkista tietoa aiheesta {agent['topic']}. {final_question}",
        "ai_disclosure": True, "operator_identity_exposed": False,
        "recipient": None, "send_ready": False, "human_review_required": True,
        "network_action": False, "publish_action": False,
        "review_notes": ["Check source context, platform rules and rate limits.",
                         "No pretending to be a human or coordinated deceptive engagement."],
    }


def parse_feed(source_id: str, raw: bytes) -> list[dict]:
    """Parse a bounded RSS/Atom response without resolving arbitrary URLs."""
    if source_id not in BY_ID:
        raise ValueError("unknown feed")
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES or not raw:
        raise ValueError("invalid RSS/Atom payload size")
    first = raw[:4096].upper()
    if b"<!DOCTYPE" in first or b"<!ENTITY" in raw.upper():
        raise ValueError("DTD and entities not supported")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValueError("invalid RSS/Atom XML") from exc
    if root.tag == "rss":
        entries = root.findall("./channel/item")
        atom = False
    elif root.tag == ATOM_NS + "feed":
        entries = root.findall(ATOM_NS + "entry")
        atom = True
    else:
        raise ValueError("not an RSS or Atom feed")
    output = []
    for item in entries[:MAX_FEED_ITEMS * 3]:
        if atom:
            get = lambda key: item.findtext(ATOM_NS + key, default="")
            links = [a.attrib.get("href", "") for a in item.findall(ATOM_NS + "link")
                     if a.attrib.get("rel", "alternate") == "alternate"]
            url = links[0] if links else ""
            title, summary, published = get("title"), get("summary") or get("content"), get("updated") or get("published")
        else:
            get = lambda key: item.findtext(key, default="")
            url = get("link")
            title, summary, published = get("title"), get("description"), get("pubDate")
        try:
            candidate = {
                "source_id": source_id,
                "courier_id": BY_ID[source_id].courier_id,
                "title": _clean(title, 240),
                "summary": _clean(summary or title, 360),
                "url": _public_article_url(url, BY_ID[source_id]),
                "published_at": _clean(published, 80) if published else None,
            }
        except ValueError:
            continue  # Fail closed for invalid links; no off-domain article URLs.
        if candidate["url"] not in {x["url"] for x in output}:
            output.append(candidate)
        if len(output) >= MAX_FEED_ITEMS:
            break
    return output


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_source(source_id: str, *, timeout: float = 8.0) -> list[dict]:
    """Explicit CLI-only, one-shot HTTPS read from the constant registry."""
    if source_id not in BY_ID:
        raise ValueError("unknown feed source")
    if type(timeout) not in (int, float) or not 1 <= timeout <= 15:
        raise ValueError("timeout out of range")
    source = BY_ID[source_id]
    opener = build_opener(ProxyHandler({}), HTTPSHandler(context=ssl.create_default_context()), _NoRedirect())
    request = Request(source.url, headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml"})
    try:
        with opener.open(request, timeout=timeout) as response:
            if response.status != 200:
                raise ValueError("feed returned non-200")
            if response.url != source.url:  # no redirects or endpoint rewriting
                raise ValueError("feed endpoint changed")
            kind = response.headers.get("Content-Type", "").lower()
            if kind and not ("xml" in kind or "text/plain" in kind):
                raise ValueError("feed content type is not XML")
            raw = response.read(MAX_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise ValueError("public feed not available: " + source_id) from exc
    return parse_feed(source_id, raw)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Explicit, bounded Limbo public-source read; no posting")
    parser.add_argument("--source", choices=sorted(BY_ID), action="append")
    parser.add_argument("--fetch", action="store_true", help="Opt in to one-shot network reads; never automatic")
    parser.add_argument("--output", required=True, help="New local JSON evidence artifact (must not exist)")
    args = parser.parse_args(argv)
    if not args.fetch:
        parser.error("--fetch is required to authorize public-source network reads")
    source_ids = list(dict.fromkeys(args.source or BY_ID.keys()))
    documents, errors = [], []
    for source_id in source_ids:
        try:
            documents.extend(fetch_source(source_id))
        except ValueError as exc:
            errors.append({"source_id": source_id, "error": str(exc)})
    # Do not manufacture a successful research run when every feed failed/returned empty.
    if not documents:
        raise SystemExit("No public feed observations; refusing to write an empty success report")
    report = analyze_documents(documents[:MAX_DOCUMENTS])
    report["fetch_errors"] = errors
    report["fetch_kind"] = "explicit_manual_cli"
    report["collected_at_utc"] = datetime.now(timezone.utc).isoformat()
    write_new_report(args.output, report)
    print(json.dumps({"path": args.output, "sources": source_ids,
                      "documents": len(report["receipts"]), "feed_errors": len(errors),
                      "session_replay_matches": report["session"].get("replay_matches")},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
