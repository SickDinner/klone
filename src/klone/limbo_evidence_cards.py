"""KLONE E11.8: auditable next-action cards for abstract/summary differences.

E11.7 must be re-derived from original seven documents, using the current
canonical Memory Core source pair, before any review card is issued.
Numbers with different units are *never* accepted as corroborating evidence.
No network, model calls, Council72 executions, votes or memory mutation.
"""
from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from pathlib import Path
import re

from .evidence_io import json_object, write_new_report
from .limbo_evidence_review import _read_input, MAX_MANIFEST_BYTES
from .limbo_arxiv_abstract_compare import compare_abstracts
from .limbo_council_workbench import _fingerprint

MAX_CARDS=40
# Fully delimited number and unit. Never equate a bare 31 with 31%, or
# 0.997 kelvin with 0.997% just because the digits overlap.
MEASURE=re.compile(
    r"(?<![\w.,])(\d{1,6}(?:[.,]\d{1,6})?)\s*"
    r"(%|prosenttiyksikköä|prosenttiyksikön|prosenttiyksikkö|"
    r"percentage points|percentage point|prosenttia|prosentin|"
    r"percent|percentage|kelviniä|kelvinin|kelvin|K)"
    r"(?![\w])",
    re.IGNORECASE,
)
UNIT={
    "%":"percent","prosenttia":"percent","prosentin":"percent",
    "percent":"percent","percentage":"percent",
    "prosenttiyksikkö":"percentage_point",
    "prosenttiyksikköä":"percentage_point",
    "prosenttiyksikön":"percentage_point",
    "percentage point":"percentage_point",
    "percentage points":"percentage_point",
    "kelviniä":"kelvin","kelvinin":"kelvin","kelvin":"kelvin","k":"kelvin",
}
PRIORITY={
    "partial_numeric_overlap_requires_primary_check":1,
    "numbers_mentioned_in_abstract_claim_not_verified":1,
    "no_match_in_abstract_full_text_check_required":2,
    "partial_keyword_overlap_not_claim_verification":3,
    "verbatim_in_arxiv_abstract_not_independent_confirmation":4,
}

def _measures(text):
    found={}
    for hit in MEASURE.finditer(text):
        try:
            value=Decimal(hit.group(1).replace(",","."))
        except InvalidOperation:
            continue
        # A bare lowercase "k" can mean k-nearest neighbours in graph
        # methods, not Kelvin. Only uppercase symbol "K" is a kelvin unit.
        if hit.group(2)=="k":
            continue
        unit=UNIT[hit.group(2).casefold()]
        normalized=format(value.normalize(),"f")
        key=(normalized,unit)
        found[key]={
            "number":normalized,"unit":unit,"surface":hit.group(),
            "char_start":hit.start(),"char_end":hit.end(),
        }
    return [found[x] for x in sorted(found)]

def _exact_spans(source,quote):
    return [{"char_start":m.start(),"char_end":m.end()}
            for m in re.finditer(re.escape(quote.strip()),source,re.IGNORECASE)
            ][:5]

def _instructions(kind,measured,missing,exact):
    actions=[
        "Check the arXiv-versioned source and confirm whether the statement is actually present in its methods/results, not just in the local paraphrase.",
        "Identify the outcome measure, evaluation dataset, baseline, uncertainty, study limitations and possible independent replication.",
    ]
    if kind=="verbatim_in_arxiv_abstract_not_independent_confirmation":
        actions.insert(0,
            "An exact string was found in the original arXiv abstract; record its location but DO NOT treat it as evidence for experimental correctness.")
    elif kind=="no_match_in_abstract_full_text_check_required":
        actions.insert(0,
            "No matching string or distinctive term in the short abstract. This is not evidence against the claim: inspect full text.")
    elif kind=="partial_keyword_overlap_not_claim_verification":
        actions.insert(0,
            "Shared terminology is not a matched claim. Cross-language Finnish-English translation may explain low overlap.")
    else:
        actions.insert(0,
            "Numbers appearing in an abstract without identical metric, units, baseline and context do not verify a claimed result.")
    if measured:
        actions.append(
            "Confirm all quantities, units (percent vs percentage points vs kelvin), metric direction, denominators, rounding and comparison baselines."
        )
    if missing:
        actions.append(
            "Some explicitly unit-labelled quantities in the local summary were not matched with the same unit in the abstract."
        )
    if exact:
        actions.append(
            "This text match is only an abstract quotation, not a check of the full paper or independent reproduction."
        )
    return actions

def build_cards(core_db,original,proposals,selected,ledger,quality,queue,
                receipt,comparison):
    if any(type(obj) is not dict for obj in (
        original,proposals,selected,ledger,quality,queue,receipt,comparison
    )):
        raise ValueError("E11.8 requires eight JSON objects")
    fresh=compare_abstracts(
        core_db,original,proposals,selected,ledger,quality,queue,receipt
    )
    if comparison!=fresh or comparison.get("report_sha256")!=_fingerprint({
        k:v for k,v in comparison.items() if k!="report_sha256"
    }):
        raise ValueError("E11.7 report is stale, tampered or from a different source chain")
    if len(fresh["comparisons"])>MAX_CARDS:
        raise ValueError("E11.8 maximum comparison count exceeded")
    pending={x["candidate_id"]:x for x in queue["queue"]}
    if len(pending)!=len(queue["queue"]):
        raise ValueError("duplicate E11.5 queue candidates")
    by_event={x["memory_event_id"]:x for x in receipt["documents"]}
    cards=[]
    for row in fresh["comparisons"]:
        candidate=pending.get(row["candidate_id"])
        doc=by_event.get(row["source_event_id"])
        if candidate is None or doc is None:
            raise ValueError("E11.8 source/candidate mismatch")
        abstract=doc["abstract_from_arxiv"]
        kind=row["comparison_class"]
        if kind not in PRIORITY:
            raise ValueError("unknown E11.7 classification")
        exact_spans=_exact_spans(abstract,row["quote"]) if row["quote_occurs_in_abstract_verbatim"] else []
        if (row["quote_occurs_in_abstract_verbatim"] and not exact_spans):
            raise ValueError("claimed arXiv abstract verbatim match is absent")
        summary_measures=_measures(row["quote"])
        abstract_measures=_measures(abstract)
        in_abstract={(x["number"],x["unit"]) for x in abstract_measures}
        matching=[x for x in summary_measures
                  if (x["number"],x["unit"]) in in_abstract]
        missing=[x for x in summary_measures
                 if (x["number"],x["unit"]) not in in_abstract]
        # Two superficially identical values with different units are not a
        # measurement match; do not reuse E11.7's untyped numeric scores.
        task_roles=[
            {"task":t["task"],"member_id":t["member_id"],
             "member_name":t["member_name"],
             "ring":t["ring"],"slot":t["slot"],
             "status":"pending_no_agent_executed"}
            for t in candidate["verification_tasks"]
        ]
        cards.append({
            "candidate_id":row["candidate_id"],
            "source":row["source"],
            "source_event_id":row["source_event_id"],
            "arxiv_id":row["arxiv_id"],
            "original_publication_url":row["source_url"],
            "abstract_sha256":doc["abstract_sha256"],
            "local_quote_sha256":sha256(row["quote"].encode("utf-8")).hexdigest(),
            "local_summary_quote":row["quote"],
            "source_content_origin":row["source_content_origin"],
            "arxiv_abstract_correspondence":kind,
            "reliability":"abstract_lexical_correspondence_only",
            "priority":PRIORITY[kind],
            "verbatim_abstract_locations":exact_spans,
            "measured_quantities_in_local_quote":summary_measures,
            "unit_consistent_numeric_mentions_in_abstract":matching,
            "not_found_as_same_unit_in_abstract":missing,
            "numbers_as_unsupported_scientific_truth":False,
            "not_found_in_abstract_is_disproof":False,
            "full_paper_checked":False,
            "scientific_claim_verified":False,
            "completed_review_count":0,
            "verification_tasks":task_roles,
            "required_next_checks":_instructions(
                kind,summary_measures,missing,bool(exact_spans)),
        })
    cards.sort(key=lambda c:(
        c["priority"],c["source"],c["candidate_id"]))
    results={
        "kind":"klone-e11-8-source-verification-cards",
        "schema_version":1,
        "source_event_ids":fresh["source_event_ids"],
        "source_snapshot_sha256":fresh["source_snapshot_sha256"],
        "e11_7_report_sha256":fresh["report_sha256"],
        "e11_6_receipt_sha256":receipt["report_sha256"],
        "card_count":len(cards),
        "source_summary_pairs":2,
        "cards":cards,
        "deferred_non_evidence_count":fresh["deferred_non_evidence_context_count"],
        "proposed_pending_council_tasks":sum(len(x["verification_tasks"]) for x in cards),
        "council_completed_reviews":0,
        "scientifically_verified_claims":0,
        "original_full_text_checked":False,
        "new_network_requests":0,
        "memory_write":False,
        "authority":{
            "autonomous_agent_execution":False,
            "council_binding_vote":False,
            "hypothesis_verified":False,
            "research_claim_verified":False,
            "memory_write":False,
            "external_network_actions":False,
            "source_full_text_authenticated":False,
        },
        "next_step":"Obtain and inspect correctly licensed original full texts; compare methods, metrics and evaluation baselines against each individual card.",
    }
    results["report_sha256"]=_fingerprint(results)
    return results

def main(argv=None):
    parser=argparse.ArgumentParser(description="KLONE E11.8 offline evidence cards")
    parser.add_argument("--klone-db",type=Path,required=True)
    for key in ("original","proposals","selected","ledger","quality",
                "queue","receipt","comparison"):
        parser.add_argument("--"+key,type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args(argv)
    try:
        docs=[
            json_object(_read_input(
                getattr(args,key),MAX_MANIFEST_BYTES,"E11.8-"+key))
            for key in ("original","proposals","selected","ledger",
                        "quality","queue","receipt","comparison")
        ]
        report=build_cards(args.klone_db,*docs)
        write_new_report(
            args.output.expanduser(),
            json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",
            Path.cwd().resolve(),
        )
    except (ValueError,PermissionError,OSError) as error:
        parser.error(str(error))
    print(json.dumps({
        "kind":report["kind"],
        "cards":report["card_count"],
        "pending_tasks":report["proposed_pending_council_tasks"],
        "scientific_truth_verified":False,
        "memory_write":False,
        "new_network_requests":0,
        "output":str(args.output),
    },ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
