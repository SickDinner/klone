"""KLONE Atlas E9: read-only source-pair dossiers from actual public Memory Core.

No internet access, source crawling, private-room reads, model hallucinations,
E7 approvals or database writes. Pairs must pass the current radar quality
gate; metadata alone never proves a claim or study independence.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

from .limbo_atlas import BY_SOURCE

from .evidence_io import write_new_report
from .limbo_discovery import radar
from .limbo_intelligence import _memories

MAX_DOSSIERS=24

# Identity is publication URL, not event ID, publisher group, or document
# title. Never merge unrelated news stories simply because titles overlap.
KNOWN_QUERY_STRIP_HOSTS=frozenset({
    "bbc.co.uk","bbc.com","arxiv.org","europepmc.org",
})


def _publication_key(doc):
    """Stable canonical public-source identity; no network or title inference."""
    u=urlsplit(doc["source_url"])
    host=(u.hostname or "").casefold().removeprefix("www.")
    path=u.path.rstrip("/") or "/"
    if u.scheme!="https" or not host or u.username or u.password:
        raise ValueError("public research source must be a valid HTTPS URL")
    # Known feed queries contain campaign tracking; retain unrecognized
    # queries, avoiding accidental conflation of distinct resources.
    query=u.query
    if host in KNOWN_QUERY_STRIP_HOSTS:
        query="&".join(q for q in query.split("&")
                       if q and not q.split("=",1)[0].casefold().startswith(
                           ("utm_","at_")))
    return (host,path,query)


def _source_class(doc):
    source=BY_SOURCE[doc["source_id"]]
    if source.kind=="arxiv":
        return ("research_preprint","preprint_peer_review_not_confirmed")
    if source.kind=="europepmc":
        return ("indexed_research","indexing_does_not_verify_method_or_peer_review")
    return ("news_or_reference_feed","not_primary_research_by_source_type")


def _collapse_source_pairs(pairs,docs):
    """Deduplicate *unordered publication pairs*, preserve all Memory IDs."""
    kept=[]
    indexes={}
    duplicates=[]
    for pair in pairs:
        a=docs[pair["first_event_id"]]
        b=docs[pair["second_event_id"]]
        aa=_publication_key(a)
        bb=_publication_key(b)
        if aa==bb:
            duplicates.append({
                "event_ids":[a["event_id"],b["event_id"]],
                "reason":"same_publication_on_both_sides",
            })
            continue
        key=tuple(sorted((aa,bb)))
        original=[a["event_id"],b["event_id"]]
        if key in indexes:
            prior=kept[indexes[key]]
            prior["duplicate_memory_event_pairs"].append(original)
            duplicates.append({
                "event_ids":original,
                "canonical_event_ids":[prior["first_event_id"],prior["second_event_id"]],
                "reason":"same_publication_pair_different_memory_events",
            })
            continue
        indexes[key]=len(kept)
        kept.append({**pair,"duplicate_memory_event_pairs":[]})
    return kept,duplicates




def _pair_lookup(report,first,second):
    for pair in report["cross_discipline_candidates"]:
        if (pair["first_event_id"],pair["second_event_id"]) in (
                (first,second),(second,first)):
            return pair
    raise ValueError("event pair is not a current quality-gated public research lead")


def _source(doc):
    return {
        "event_id":doc["event_id"],
        "article_id":doc["article_id"],
        "version":doc["version"],
        "revision_id":doc["revision_id"],
        "source_id":doc["source_id"],
        "domain":doc["domain"],
        "source_kind":BY_SOURCE[doc["source_id"]].kind,
        "source_class":_source_class(doc)[0],
        "source_class_caution":_source_class(doc)[1],
        "publisher_group":doc["publisher_group"],
        "title":doc["title"],
        "source_excerpt":doc["abstract"][:450],
        "source_url":doc["source_url"],
        "published_at":doc["published_at"],
        "receipt_sha256":doc["receipt_sha256"],
        "epistemic_status":"unverified_publisher_claim",
        "full_text_reviewed":False,
        "study_design_verified":False,
    }


def _make(pair,docs):
    first=docs[pair["first_event_id"]]
    second=docs[pair["second_event_id"]]
    same_publisher=first["publisher_group"]==second["publisher_group"]
    return {
        "kind":"klone-atlas-e9-pair-dossier",
        "schema_version":1,
        "source_a":_source(first),
        "source_b":_source(second),
        "common_non_generic_terms":pair["shared_terms"],
        "concepts_in_both_titles":pair["shared_title_concepts"],
        "quality_gate":pair["quality_gate"],
        "radar_review_priority":pair["candidate_priority"],
        "pair_justification":pair["justification"],
        "duplicate_memory_event_pairs":pair.get("duplicate_memory_event_pairs",[]),
        "source_comparison_type":(
            "research_metadata_pair"
            if all(_source_class(doc)[0]!="news_or_reference_feed"
                   for doc in (first,second))
            else "mixed_news_or_reference_pair"
        ),
        "source_comparison_caution":(
            "An RSS news/reference item is not a second independent study."
            if any(_source_class(doc)[0]=="news_or_reference_feed"
                   for doc in (first,second))
            else "Two research-indexed items do not establish independent evidence."
        ),
        "independence":{"same_publisher_group":same_publisher,
                        "different_publisher_groups":not same_publisher,
                        "independent_studies_confirmed":False,
                        "shared_dataset_checked":False,
                        "preprint_duplicate_checked":False},
        "research_protocol":{
            "shared_question":"What exactly is the common measurable scientific construct?",
            "falsifier":"What independent measurement would refute the suggested connection?",
            "source_a_methods":"Open original publication; extract design, sample, population, measures and limitations.",
            "source_b_methods":"Open original publication; extract design, sample, population, measures and limitations.",
            "overlap_check":"Check authors, shared datasets, publications, preprint versions and citations.",
            "alternative_explanation":"Test whether terminology merely reflects a generic method or unrelated use.",
            "replication":"Find independent methods and data that could reproduce the claimed observation.",
        },
        "limitations":["Only stored public publisher metadata and excerpts were inspected.",
                       "The complete papers have not been read.",
                       "Shared vocabulary does not imply compatible methods, results or causality.",
                       "No primary dataset, independent replication or counterevidence was verified."],
        "epistemic_status":"unverified_research_lead",
        "scientific_truth_verified":False,
        "memory_write":False,
        "external_network_actions":False,
        "private_memory_access":False,
    }


def review_pair(core_db,first_event_id,second_event_id,*,question="genetiikka",
                limit=48):
    if (type(first_event_id) is not int or type(second_event_id) is not int
        or first_event_id<=0 or second_event_id<=0
        or first_event_id==second_event_id):
        raise ValueError("two distinct positive public research event IDs required")
    report=radar(core_db,question,limit=limit)
    pair=_pair_lookup(report,first_event_id,second_event_id)
    docs={d["event_id"]:d for d in _memories(core_db)}
    if first_event_id not in docs or second_event_id not in docs:
        raise ValueError("source event is not current in public research-room")
    return _make(pair,docs)


def review_all(core_db,*,question="genetiikka",limit=48):
    report=radar(core_db,question,limit=limit)
    docs={d["event_id"]:d for d in _memories(core_db)}
    raw=report["cross_discipline_candidates"][:MAX_DOSSIERS]
    sources,duplicates=_collapse_source_pairs(raw,docs)
    dossiers=[_make(pair,docs) for pair in sources]
    return {
        "kind":"klone-atlas-e9-review-batch",
        "schema_version":2,"question":question,
        "public_memory_count":len(docs),
        "quality_gate":report["diagnostics"]["quality_gate"],
        "raw_memory_pair_count":len(raw),
        "duplicate_memory_pair_count":len(duplicates),
        "duplicate_memory_pairs":duplicates,
        "candidate_count":len(dossiers),
        "source_type_counts":{
            "research_metadata_pairs":sum(
                x["source_comparison_type"]=="research_metadata_pair"
                for x in dossiers),
            "mixed_news_or_reference_pairs":sum(
                x["source_comparison_type"]=="mixed_news_or_reference_pair"
                for x in dossiers),
        },
        "dossiers":dossiers,
        "memory_write":False,"external_network_actions":False,
        "scientific_truth_verified":False,
    }


def main(argv=None):
    p=argparse.ArgumentParser(description="KLONE E9 read-only public research source dossiers")
    p.add_argument("--klone-db",type=Path,required=True)
    p.add_argument("--question",default="genetiikka")
    p.add_argument("--limit",type=int,default=48)
    option=p.add_mutually_exclusive_group(required=True)
    option.add_argument("--all",action="store_true")
    option.add_argument("--pair",type=int,nargs=2,metavar=("FIRST","SECOND"))
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args(argv)
    try:
        result=(review_all(args.klone_db,question=args.question,limit=args.limit)
                if args.all else
                review_pair(args.klone_db,*args.pair,question=args.question,limit=args.limit))
        write_new_report(args.output.expanduser(),
                         json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+"\n",
                         Path.cwd().resolve())
    except (ValueError,PermissionError,OSError) as exc:
        p.error(str(exc))
    print(json.dumps({"kind":result["kind"],
                      "dossiers":len(result.get("dossiers",[result])),
                      "memory_write":False,"output":str(args.output)},ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
