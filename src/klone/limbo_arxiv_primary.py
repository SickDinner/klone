"""KLONE E11.6: owner-authorized, bounded arXiv Atom metadata receipts.

This fetches publication metadata/abstract, NOT full papers.  No arbitrary
URLs, redirects, source-content uploads, council actions or main DB writes.
An arXiv abstract is *not* independent replication or proven scientific fact.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
from urllib.parse import quote, urlsplit
from urllib.request import (
    build_opener, HTTPRedirectHandler, HTTPSHandler, ProxyHandler, Request,
)
from urllib.error import HTTPError, URLError
import xml.etree.ElementTree as ET

from .evidence_io import write_new_report
from .limbo_council_workbench import council_review, _fingerprint

ATOM_NS = "{http://www.w3.org/2005/Atom}"
MAX_ATOM_BYTES = 256*1024
MAX_ABSTRACT_CHARS = 12000
MAX_TITLE_CHARS = 500
ARXIV_ID = re.compile(r"^[0-9]{4}\.[0-9]{4,5}v[1-9][0-9]*$")
ARXIV_ABS_PATH = re.compile(r"^/abs/([0-9]{4}\.[0-9]{4,5}v[1-9][0-9]*)$")
API_HOST = "export.arxiv.org"


class _DenyRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _source_ids(board):
    if type(board) is not dict or board.get("seat_count")!=72:
        raise ValueError("current canonical Council72 research board required")
    items=[]
    for label in ("source_a","source_b"):
        source=board["source_summary"][label]
        parsed=urlsplit(source["source_url"])
        if (parsed.scheme!="https" or parsed.hostname!="arxiv.org"
            or parsed.username is not None or parsed.password is not None
            or parsed.port is not None or parsed.query or parsed.fragment):
            raise ValueError("E11.6 only allows exact HTTPS arxiv.org/abs/versioned-id sources")
        match=ARXIV_ABS_PATH.fullmatch(parsed.path)
        if match is None:
            raise ValueError("E11.6 requires versioned arXiv publication paths")
        article=match.group(1)
        if not ARXIV_ID.fullmatch(article):
            raise ValueError("unrecognized arXiv article ID")
        items.append({
            "event_id":source["event_id"],
            "arxiv_id":article,
            "source_url":source["source_url"],
            "memory_title":source["title"],
            "memory_receipt_sha256":source["receipt_sha256"],
            "memory_version":source["version"],
        })
    if items[0]["arxiv_id"]==items[1]["arxiv_id"]:
        raise ValueError("cannot use the same arXiv publication twice")
    return items


def prepare(core_db,first,second,*,question="genetiikka"):
    board=council_review(core_db,first,second,question=question)
    entries=_source_ids(board)
    result={
        "kind":"klone-e11-6-arxiv-metadata-plan",
        "schema_version":1,
        "source_event_ids":[s["event_id"] for s in entries],
        "source_snapshot_sha256":board["source_snapshot_sha256"],
        "sources":entries,
        "requests_planned":1,
        "remote_host_allowlist":[API_HOST],
        "network_performed":False,
        "owner_network_authorization":False,
        "scientific_truth_verified":False,
        "primary_full_text_fetched":False,
        "memory_write":False,
    }
    result["report_sha256"]=_fingerprint(result)
    return result


def _atom_url(entries):
    ids=",".join(item["arxiv_id"] for item in entries)
    return "https://export.arxiv.org/api/query?id_list="+quote(ids,safe=",")+"&max_results=2"


def _get_feed(url):
    if url != _atom_url_from_url(url):
        raise ValueError("unexpected arXiv metadata API request URL")
    # Ignore environment proxies; use platform HTTPS certificate validation.
    opener=build_opener(ProxyHandler({}), HTTPSHandler(), _DenyRedirect())
    request=Request(url,headers={
        "User-Agent":"KLONE-Research-Metadata/0.1 (owner-authorized, read-only)",
        "Accept":"application/atom+xml, application/xml;q=0.9",
    },method="GET")
    try:
        with opener.open(request,timeout=20) as response:
            if response.status!=200 or response.geturl()!=url:
                raise ValueError("arXiv returned non-200 or redirected metadata response")
            content_type=response.headers.get_content_type()
            if content_type not in ("application/atom+xml","application/xml","text/xml","text/plain"):
                raise ValueError("unexpected arXiv response content type")
            length=response.headers.get("Content-Length")
            if length is not None and int(length)>MAX_ATOM_BYTES:
                raise ValueError("arXiv metadata response exceeds limit")
            body=response.read(MAX_ATOM_BYTES+1)
    except (HTTPError,URLError,TimeoutError,OSError) as exc:
        raise ValueError("arXiv metadata request failed without modifying KLONE") from exc
    if len(body)>MAX_ATOM_BYTES:
        raise ValueError("arXiv Atom feed exceeds bounded response size")
    return body


def _atom_url_from_url(url):
    # Defensive canonical check; caller can only build this from arXiv IDs.
    parsed=urlsplit(url)
    if (parsed.scheme!="https" or parsed.hostname!=API_HOST
        or parsed.path!="/api/query" or parsed.username is not None
        or parsed.password is not None or parsed.port is not None or parsed.fragment):
        raise ValueError("arXiv metadata URL must be exact HTTPS allowlist")
    if not re.fullmatch(
        r"id_list=[0-9]{4}\.[0-9]{4,5}v[1-9][0-9]*,"
        r"[0-9]{4}\.[0-9]{4,5}v[1-9][0-9]*&max_results=2",
        parsed.query,
    ):
        raise ValueError("arXiv metadata URL has unexpected parameters")
    return url


def _field(node,key):
    child=node.find(ATOM_NS+key)
    return "" if child is None or child.text is None else child.text.strip()


def _clean(text):
    return " ".join(text.split())


def parse_atom(raw,entries):
    if type(raw) is not bytes or not raw or len(raw)>MAX_ATOM_BYTES:
        raise ValueError("invalid bounded arXiv Atom payload")
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("XML entities and DTDs are not supported")
    try:
        root=ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValueError("invalid arXiv Atom response") from exc
    if root.tag!=ATOM_NS+"feed":
        raise ValueError("arXiv response must be an Atom feed")
    nodes=root.findall(ATOM_NS+"entry")
    if len(nodes)!=2:
        raise ValueError("expected exactly two primary-source arXiv entries")
    requested={x["arxiv_id"]:x for x in entries}
    observed={}
    for node in nodes:
        entry_id=_field(node,"id")
        parsed=urlsplit(entry_id)
        if (parsed.hostname!="arxiv.org" or parsed.scheme not in ("http","https")
            or parsed.username is not None or parsed.password is not None
            or parsed.query or parsed.fragment):
            raise ValueError("untrusted arXiv entry identity")
        found=ARXIV_ABS_PATH.fullmatch(parsed.path)
        if found is None or found.group(1) not in requested:
            raise ValueError("arXiv entry ID does not match requested version")
        key=found.group(1)
        if key in observed:
            raise ValueError("duplicate arXiv entry identity")
        title=_clean(_field(node,"title"))
        abstract=_clean(_field(node,"summary"))
        if not (5<=len(title)<=MAX_TITLE_CHARS and
                30<=len(abstract)<=MAX_ABSTRACT_CHARS):
            raise ValueError("arXiv entry title or abstract out of bounds")
        expected_title=_clean(requested[key]["memory_title"])
        title_match=(title.casefold().rstrip(" .")==expected_title.casefold().rstrip(" ."))
        observed[key]={
            "arxiv_id":key,
            "source_url":requested[key]["source_url"],
            "memory_event_id":requested[key]["event_id"],
            "memory_receipt_sha256":requested[key]["memory_receipt_sha256"],
            "atom_entry_id":entry_id,
            "atom_published":_field(node,"published"),
            "atom_updated":_field(node,"updated"),
            "title_from_arxiv":title,
            "title_matches_memory":title_match,
            "abstract_from_arxiv":abstract,
            "abstract_sha256":sha256(abstract.encode("utf-8")).hexdigest(),
            "abstract_content":"remote_arxiv_atom_not_peer_reviewed_or_independently_replicated",
            "publisher_full_text_authenticated":False,
            "scientific_truth_verified":False,
        }
    if set(observed)!=set(requested):
        raise ValueError("missing requested arXiv source ID")
    return [observed[x["arxiv_id"]] for x in entries]


def fetch(core_db,first,second,*,question="genetiikka",
          owner_authorizes_public_read=False):
    if owner_authorizes_public_read is not True:
        raise ValueError("network fetch requires explicit owner approval")
    plan=prepare(core_db,first,second,question=question)
    url=_atom_url(plan["sources"])
    raw=_get_feed(url)
    documents=parse_atom(raw,plan["sources"])
    result={
        "kind":"klone-e11-6-arxiv-metadata-receipts",
        "schema_version":1,
        "source_event_ids":plan["source_event_ids"],
        "source_snapshot_sha256":plan["source_snapshot_sha256"],
        "request_url":url,
        "remote_host":API_HOST,
        "atom_response_sha256":sha256(raw).hexdigest(),
        "atom_response_bytes":len(raw),
        "documents":documents,
        "network_performed":True,
        "owner_network_authorization":True,
        "metadata_title_pair_matches_memory":all(
            item["title_matches_memory"] for item in documents),
        "metadata_obtained_from_arxiv_atom":True,
        "primary_full_text_fetched":False,
        "independent_research_verification":False,
        "scientific_truth_verified":False,
        "council_reviews_performed":0,
        "memory_write":False,
    }
    result["report_sha256"]=_fingerprint(result)
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description="KLONE E11.6 version-pinned arXiv metadata receipts")
    p.add_argument("--klone-db",type=Path,required=True)
    p.add_argument("--pair",nargs=2,type=int,required=True,metavar=("FIRST","SECOND"))
    p.add_argument("--question",default="genetiikka")
    p.add_argument("--fetch",action="store_true")
    p.add_argument("--owner-authorizes-public-read",action="store_true")
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args(argv)
    try:
        if args.owner_authorizes_public_read and not args.fetch:
            raise ValueError("--owner-authorizes-public-read is only valid with --fetch")
        result=(fetch(args.klone_db,*args.pair,question=args.question,
                      owner_authorizes_public_read=args.owner_authorizes_public_read)
                if args.fetch else prepare(args.klone_db,*args.pair,question=args.question))
        write_new_report(
            args.output.expanduser(),
            json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+"\n",
            Path.cwd().resolve(),
        )
    except (ValueError,OSError,PermissionError) as exc:
        p.error(str(exc))
    print(json.dumps({
        "kind":result["kind"],
        "network_performed":result["network_performed"],
        "arxiv_sources":len(result.get("sources",result.get("documents",[]))),
        "primary_full_text_fetched":False,
        "scientific_truth_verified":False,
        "memory_write":False,
        "output":str(args.output),
    },ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
