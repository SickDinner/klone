"""KLONE E11.2: offline *candidate* extraction from owner-controlled text.

Only reads the current E11 manifest and a canonical public Memory Core pair.
Lexical heuristics never establish validity, original paper authorship,
scientific agreement/disagreement, or actual Council72 review completion.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re

from .evidence_io import json_object, read_bounded, write_new_report
from .limbo_council_workbench import council_review, _fingerprint
from .limbo_evidence_review import MAX_MANIFEST_BYTES, _read_input, review_manifest

MAX_PER_SOURCE=12
MAX_QUOTE_CHARS=280
MIN_QUOTE_CHARS=24

# Label only the topic needing examination, not a conclusion or evidentiary stance.
MARKERS={
    "limitations":("limitation","limitations","uncertainty","bias","overfit",
                   "drawback","caveat","rajoitu","epävarm","vinoum","ylisovit"),
    "results":("results","result","finding","findings","performance",
               "accuracy","improv","evaluat","tulok","havaitt","tarkkuus",
               "suoritus","vertail"),
    "methods":("method","methodology","dataset","cohort","sample","model",
               "training","measurement","network","graph","experiment",
               "menetel","aineisto","otos","verkko","graaf","mitta",
               "koulutu","kokeil"),
}
PRIORITY={"limitations":4,"results":3,"methods":2,"context":1}
REVIEWER_SEAT={
    "limitations":(5,3),  # selection-bias and adverse-interpretation risks
    "results":(6,6),     # negative findings
    "methods":(6,1),     # research design
    "context":(8,3),     # evidence burden
}
SUMMARY_MARKERS=("selostus","referaat","tiivistelmä","summary","paraphrase",
                 "ai-generated","tekoäly","referoitu","ei varmennettu")


def _category(quote):
    folded=quote.casefold()
    for kind in ("limitations","results","methods"):
        if any(marker in folded for marker in MARKERS[kind]):
            return kind
    return "context"


def _segments(text):
    """Return only unambiguous verbatim excerpts with original Unicode offsets."""
    for line in re.finditer(r"[^\r\n]+",text):
        for sentence in re.finditer(r"[^.!?]+[.!?]*",line.group()):
            raw=sentence.group()
            left=len(raw)-len(raw.lstrip())
            right=len(raw.rstrip())
            if left>=right:
                continue
            start=line.start()+sentence.start()+left
            end=line.start()+sentence.start()+right
            quote=text[start:end]
            if not MIN_QUOTE_CHARS<=len(quote)<=MAX_QUOTE_CHARS:
                continue
            if text.count(quote)!=1:
                continue
            yield start,end,quote


def suggest(core_db,manifest,*,per_source_limit=8):
    if type(per_source_limit) is not int or not 1<=per_source_limit<=MAX_PER_SOURCE:
        raise ValueError("per_source_limit must be between 1 and 12")
    # Revalidates exact Memory Core event IDs, original URLs/titles/receipts,
    # owner attestations and bounded texts; never trusts the manifest alone.
    validated=review_manifest(core_db,manifest)
    sources=manifest["sources"]
    board=council_review(core_db,
                         sources["A"]["event_id"],sources["B"]["event_id"],
                         question=manifest["question"])
    seats={(s["ring"],s["slot"]):s for s in board["assigned_seats"]}
    all_candidates=[]
    source_info={}
    for role in ("A","B"):
        src=sources[role]
        text=src["text"]
        origin="owner_declared_summary_unverified" if any(
            tag in src["usage_rights_note"].casefold() for tag in SUMMARY_MARKERS
        ) else "owner_supplied_text_unverified"
        source_info[role]={
            "source_event_id":src["event_id"],
            "title":src["title"],
            "source_url":src["source_url"],
            "source_class":src["source_class"],
            "source_text_sha256":sha256(text.encode("utf-8")).hexdigest(),
            "source_text_characters":len(text),
            "content_origin":origin,
            "publisher_full_text_authenticated":False,
        }
        pool=[]
        for start,end,quote in _segments(text):
            category=_category(quote)
            seat=seats[REVIEWER_SEAT[category]]
            excerpt_hash=sha256(quote.encode("utf-8")).hexdigest()
            candidate_id=sha256(
                f"{src['event_id']}:{start}:{end}:{excerpt_hash}".encode()
            ).hexdigest()[:20]
            pool.append({
                "candidate_id":candidate_id,
                "source":role,
                "source_event_id":src["event_id"],
                "topic_for_review":category,
                "suggested_stance":"context",
                "suggestion_method":"lexical_heuristic_not_semantic_inference",
                "quote":quote,
                "quote_sha256":excerpt_hash,
                "source_text_sha256":source_info[role]["source_text_sha256"],
                "offset_type":"unicode_character",
                "char_start":start,"char_end":end,
                "proposed_reviewer":{
                    "member_id":seat["member_id"],
                    "member_name":seat["member_name"],
                    "ring":seat["ring"],"slot":seat["slot"],
                    "review_task":seat["review_task"],
                    "state":"pending_not_executed",
                },
                "quote_matched_owner_text":True,
                "quote_authenticated_against_publisher":False,
                "scientific_truth_verified":False,
                "review_completed":False,
            })
        # Stable order: retain relevant candidate topics without allowing one
        # long paragraph to monopolize the bounded review queue.
        chosen=sorted(pool,key=lambda c:(
            -PRIORITY[c["topic_for_review"]],c["char_start"],
            c["candidate_id"]))[:per_source_limit]
        all_candidates.extend(sorted(chosen,key=lambda c:c["char_start"]))
    result={
        "kind":"klone-e11-2-evidence-review-candidates",
        "schema_version":1,
        "question":manifest["question"],
        "per_source_limit":per_source_limit,
        "source_snapshot_sha256":validated["source_snapshot_sha256"],
        "source_event_ids":validated["source_event_ids"],
        "source_info":source_info,
        "annotation_count":validated["annotation_count"],
        "candidate_count":len(all_candidates),
        "candidates":all_candidates,
        "open_checks":[
            "Confirm whether the owner-supplied text is a summary or exact primary-source excerpt.",
            "Open both original publications before assessing the claims or method transfer.",
            "Check sample sizes, measured endpoints, competing explanations, and independent datasets.",
            "Human review must explicitly approve any later annotation or evidence stance.",
        ],
        "reviewer_assignment_state":"proposed_not_performed",
        "council_vote_count":0,
        "council_completed_reviews":0,
        "source_texts_embedded":False,
        "authority":{
            "memory_write":False,
            "external_network_actions":False,
            "private_room_access":False,
            "automatic_evidence_promotions":False,
            "scientific_truth_verified":False,
            "owner_approval":False,
            "binding_council_vote":False,
        },
    }
    result["report_sha256"]=_fingerprint(result)
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(
        description="KLONE E11.2: offline exact-quote proposals, no approvals"
    )
    parser.add_argument("--klone-db",type=Path,required=True)
    parser.add_argument("--manifest",type=Path,required=True)
    parser.add_argument("--per-source-limit",type=int,default=8)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args(argv)
    try:
        data=suggest(
            args.klone_db,
            json_object(_read_input(
                args.manifest,MAX_MANIFEST_BYTES,"E11.2-syötemanifesti")),
            per_source_limit=args.per_source_limit,
        )
        write_new_report(args.output.expanduser(),
                         json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+"\n",
                         Path.cwd().resolve())
    except (ValueError,PermissionError,OSError) as exc:
        parser.error(str(exc))
    print(json.dumps({
        "kind":data["kind"],
        "candidate_count":data["candidate_count"],
        "completed_reviews":0,"scientific_truth_verified":False,
        "memory_write":False,"output":str(args.output),
    },ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
