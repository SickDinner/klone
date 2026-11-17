"""KLONE E11.7: offline abstract-to-owner-summary correspondence audit.

Checks seven existing, locally owned reports against the current canonical
public research pair. Never fetches network, changes Memory Core, verifies
paper methods, or promotes any claim to scientific truth.

An arXiv *abstract* can support text correspondence, not independent
replication, full-paper verification, or causal inference.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from .evidence_io import json_object,write_new_report
from .limbo_arxiv_primary import (
    API_HOST, MAX_ABSTRACT_CHARS, _atom_url, _source_ids, _atom_url_from_url,
)
from .limbo_council_workbench import council_review, _fingerprint
from .limbo_evidence_review import MAX_MANIFEST_BYTES,_read_input
from .limbo_evidence_verification_queue import build_queue

WORD=re.compile(r"[^\W_]+",re.UNICODE)
NUMBER=re.compile(r"(?<![\w.])\d+(?:[.,]\d+)?(?:\s*%)?(?![\w.])")
IGNORE_TERMS=frozenset({
    "about","after","again","against","among","analyzing","and","are",
    "based","between","data","does","from","have","into","method",
    "methods","model","models","more","not","only","paper","report",
    "results","study","such","than","that","their","these","they",
    "this","those","through","using","when","where","which","with",
    "automaattinen","ilman","joiden","kaksi","kanssa","kuin","kuten",
    "malli","mallin","menetelmä","menetelmän","mukaan","myös","ovat",
    "sekä","siitä","siinä","tämä","tämän","tutkimus","tutkimuksen",
    "vaan","voidaan","vertailussa","verkko","verkon",
})
MAX_COMPARISONS=40

def _numbers(text):
    return sorted({m.group().replace(" ","").replace(",",".")
                   for m in NUMBER.finditer(text)})

def _distinctive_words(text):
    return {w for w in (m.group().casefold() for m in WORD.finditer(text))
            if len(w)>=5 and w not in IGNORE_TERMS and not w.isdecimal()}

def _validate_receipt(board,receipt):
    if type(receipt) is not dict or (
        receipt.get("kind")!="klone-e11-6-arxiv-metadata-receipts"
        or type(receipt.get("schema_version")) is not int
        or receipt.get("schema_version")!=1
        or receipt.get("network_performed") is not True
        or receipt.get("owner_network_authorization") is not True
        or receipt.get("metadata_obtained_from_arxiv_atom") is not True
        or receipt.get("primary_full_text_fetched") is not False
        or receipt.get("independent_research_verification") is not False
        or receipt.get("scientific_truth_verified") is not False
        or receipt.get("memory_write") is not False
        or receipt.get("council_reviews_performed")!=0
    ):
        raise ValueError("invalid or unsafe E11.6 arXiv receipt state")
    if receipt.get("report_sha256")!=_fingerprint({
        k:v for k,v in receipt.items() if k!="report_sha256"
    }):
        raise ValueError("E11.6 arXiv receipt digest mismatch")
    sources=_source_ids(board)
    if (receipt.get("source_event_ids")!=[s["event_id"] for s in sources]
        or receipt.get("source_snapshot_sha256")!=board["source_snapshot_sha256"]
        or receipt.get("remote_host")!=API_HOST
        or receipt.get("request_url")!=_atom_url(sources)):
        raise ValueError("E11.6 receipt does not match the current canonical pair")
    _atom_url_from_url(receipt["request_url"])
    documents=receipt.get("documents")
    if type(documents) is not list or len(documents)!=2:
        raise ValueError("E11.6 must contain exactly two source abstracts")
    if receipt.get("metadata_title_pair_matches_memory") is not True:
        raise ValueError("E11.6 titles disagree with source memory")
    mapped={}
    for source,doc in zip(sources,documents):
        if type(doc) is not dict:
            raise ValueError("invalid arXiv abstract document")
        if any((
            doc.get("memory_event_id")!=source["event_id"],
            doc.get("arxiv_id")!=source["arxiv_id"],
            doc.get("source_url")!=source["source_url"],
            doc.get("memory_receipt_sha256")!=source["memory_receipt_sha256"],
            doc.get("title_matches_memory") is not True,
            doc.get("publisher_full_text_authenticated") is not False,
            doc.get("scientific_truth_verified") is not False,
            doc.get("abstract_content")!="remote_arxiv_atom_not_peer_reviewed_or_independently_replicated",
        )):
            raise ValueError("arXiv version, source ID, or original receipt mismatch")
        atom_id=urlsplit(doc.get("atom_entry_id",""))
        if (atom_id.scheme not in ("http","https")
            or atom_id.hostname!="arxiv.org"
            or atom_id.username is not None or atom_id.password is not None
            or atom_id.query or atom_id.fragment
            or atom_id.path!="/abs/"+source["arxiv_id"]):
            raise ValueError("invalid arXiv Atom entry identity")
        title=doc.get("title_from_arxiv")
        summary=doc.get("abstract_from_arxiv")
        if (type(title) is not str or type(summary) is not str
            or not 5<=len(title)<=500
            or not 30<=len(summary)<=MAX_ABSTRACT_CHARS
            or title.casefold().strip().rstrip(" .")
               !=source["memory_title"].casefold().strip().rstrip(" .")
            or doc.get("abstract_sha256")!=sha256(summary.encode("utf-8")).hexdigest()):
            raise ValueError("arXiv title or abstract hash does not match source receipt")
        mapped[source["event_id"]]=doc
    if len(mapped)!=2:
        raise ValueError("duplicate arXiv source identity")
    return mapped

def compare_abstracts(core_db,original,proposals,selected,ledger,quality,queue,receipt):
    if any(type(x) is not dict for x in (
        original,proposals,selected,ledger,quality,queue,receipt
    )):
        raise ValueError("E11.7 expects seven JSON report objects")
    expected=build_queue(core_db,original,proposals,selected,ledger,quality)
    if queue!=expected or queue.get("report_sha256")!=_fingerprint({
        k:v for k,v in queue.items() if k!="report_sha256"
    }):
        raise ValueError("E11.5 queue differs from verified source replay")
    board=council_review(core_db,*expected["source_event_ids"],
                         question=original["question"])
    if (board["source_snapshot_sha256"]!=expected["source_snapshot_sha256"]
        or len(expected["queue"])>MAX_COMPARISONS):
        raise ValueError("stale or oversized E11.5 source queue")
    docs=_validate_receipt(board,receipt)
    comparisons=[]
    counts={}
    for item in expected["queue"]:
        doc=docs.get(item["source_event_id"])
        if doc is None or doc["source_url"]!=item["source_url"]:
            raise ValueError("queue quote does not match the corresponding arXiv article")
        abstract=doc["abstract_from_arxiv"]
        quote=item["quote"]
        exact=quote.casefold().strip() in abstract.casefold()
        tokens=_distinctive_words(abstract)&_distinctive_words(quote)
        matches=sorted(tokens)[:16]
        quoted_numbers=_numbers(quote)
        in_abstract=_numbers(abstract)
        numeric_hits=[n for n in quoted_numbers if n in in_abstract]
        numeric_unmatched=[n for n in quoted_numbers if n not in in_abstract]
        if exact:
            category="verbatim_in_arxiv_abstract_not_independent_confirmation"
        elif quoted_numbers and len(numeric_hits)==len(quoted_numbers):
            category="numbers_mentioned_in_abstract_claim_not_verified"
        elif numeric_hits:
            category="partial_numeric_overlap_requires_primary_check"
        elif matches:
            category="partial_keyword_overlap_not_claim_verification"
        else:
            category="no_match_in_abstract_full_text_check_required"
        counts[category]=counts.get(category,0)+1
        comparisons.append({
            "candidate_id":item["candidate_id"],
            "source":item["source"],
            "source_event_id":item["source_event_id"],
            "arxiv_id":doc["arxiv_id"],
            "source_url":doc["source_url"],
            "quote_sha256":item["quote_sha256"],
            "quote":quote,
            "source_content_origin":item["source_content_origin"],
            "arxiv_abstract_sha256":doc["abstract_sha256"],
            "comparison_class":category,
            "quote_occurs_in_abstract_verbatim":exact,
            "overlapping_distinctive_terms":matches,
            "numbers_in_local_quote":quoted_numbers,
            "numbers_seen_in_abstract":numeric_hits,
            "numbers_not_seen_in_abstract":numeric_unmatched,
            "absence_from_abstract_is_disproof":False,
            "publisher_full_text_checked":False,
            "claim_verified":False,
            "council_review_completed":False,
            "status":"needs_independent_full_text_or_methods_review",
        })
    result={
        "kind":"klone-e11-7-arxiv-abstract-correspondence",
        "schema_version":1,
        "source_event_ids":expected["source_event_ids"],
        "source_snapshot_sha256":expected["source_snapshot_sha256"],
        "e11_5_report_sha256":expected["report_sha256"],
        "e11_6_report_sha256":receipt["report_sha256"],
        "arxiv_atom_response_sha256":receipt["atom_response_sha256"],
        "abstracts_from_arxiv_atom":2,
        "local_quotes_compared":len(comparisons),
        "deferred_non_evidence_context_count":len(expected["deferred"]),
        "comparison_counts":dict(sorted(counts.items())),
        "comparisons":comparisons,
        "confirmed_scientific_claims":0,
        "independent_council_reviews":0,
        "full_text_papers_checked":0,
        "new_network_requests":0,
        "memory_write":False,
        "authority":{
            "scientific_truth_verified":False,
            "source_full_text_verified":False,
            "automatic_hypothesis_promotion":False,
            "binding_vote":False,
            "write_memory":False,
            "fetch_more":False,
        },
        "interpretation":"Text matching to arXiv abstracts only: not an independent replication, full-paper check, or claim verification. Missing abstract text cannot refute a paper.",
    }
    result["report_sha256"]=_fingerprint(result)
    return result

def main(argv=None):
    p=argparse.ArgumentParser(description="KLONE E11.7 offline arXiv abstract/text correspondence")
    p.add_argument("--klone-db",type=Path,required=True)
    for name in ("original","proposals","selected","ledger","quality","queue","receipt"):
        p.add_argument("--"+name,type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args(argv)
    try:
        files=[json_object(_read_input(
            getattr(args,name),MAX_MANIFEST_BYTES,"E11.7-"+name))
            for name in ("original","proposals","selected","ledger","quality","queue","receipt")]
        result=compare_abstracts(args.klone_db,*files)
        write_new_report(args.output.expanduser(),
                         json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+"\n",
                         Path.cwd().resolve())
    except (ValueError,OSError,PermissionError) as exc:
        p.error(str(exc))
    print(json.dumps({
        "kind":result["kind"],
        "compared":result["local_quotes_compared"],
        "comparison_counts":result["comparison_counts"],
        "confirmed_scientific_claims":0,
        "new_network_requests":0,
        "memory_write":False,
        "output":str(args.output),
    },ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
