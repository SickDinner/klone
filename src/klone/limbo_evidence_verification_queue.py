"""KLONE E11.5: provenance-gated research verification work queue.

E11.4's 16 owner-selected context quotes can yield only pending jobs.
All five existing E11/E11.2/E11.3/E11.4 documents are replayed before
any task is proposed. Never claim an independently authenticated paper,
a performed Council72 evaluation, scientific proof, votes, or memory writes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from .evidence_io import json_object, write_new_report
from .limbo_council_workbench import _fingerprint, council_review
from .limbo_evidence_review import MAX_MANIFEST_BYTES, _read_input
from .limbo_evidence_quality import audit_quality

ACTIONABLE = {
    "attributed_research_claim_needs_primary_check": 1,
    "unverified_context_needs_primary_check": 2,
}
DEFERRED = {
    "publication_title_not_evidence",
    "open_question_not_evidence",
    "editorial_caution_not_evidence",
}
MAX_QUEUE_ITEMS = 40

def _verification_questions(row, topic):
    checks = [
        "Find the purported excerpt in the original published paper or arXiv version and record an exact source-text anchor.",
        "Check whether the original publication contains this finding or whether it appears only in the owner-supplied summary.",
        "Identify independent data, corrections, and limitations before any scientific conclusion.",
    ]
    if row["kind"] == "attributed_research_claim_needs_primary_check":
        checks.append(
            "Compare the claimed result and its exact measurement against figures, tables, controls, and statistical uncertainty."
        )
    if topic == "methods":
        checks.append(
            "Compare model inputs, training/test split, population or geographic domain, baselines and ablations."
        )
    elif topic == "results":
        checks.append(
            "Verify named metrics, directions, denominators and evaluation datasets in primary-source results."
        )
    elif topic == "limitations":
        checks.append(
            "Find explicit failure cases, missing-data assumptions and unresolved sources of bias."
        )
    if re.search(r"(?<!\w)\d+(?:[.,]\d+)?\s*(?:%|prosent(?:tia)?|kelvin|rmse)(?!\w)",
                 row["quote"],flags=re.IGNORECASE):
        checks.append(
            "Check numerical units, rounding, baseline, study setting and uncertainty for any quoted numbers."
        )
    return checks

def build_queue(core_db, original, proposals, selected, ledger, quality):
    if any(type(x) is not dict for x in
           (original,proposals,selected,ledger,quality)):
        raise ValueError("E11.5 expects five JSON document objects")
    recomputed = audit_quality(core_db,selected,ledger,original,proposals)
    if quality != recomputed or quality.get("report_sha256") != _fingerprint({
        k:v for k,v in quality.items() if k != "report_sha256"
    }):
        raise ValueError("E11.4 quality report differs from verified four-file replay")
    board = council_review(
        core_db,*recomputed["source_event_ids"],question=original["question"]
    )
    if recomputed["source_snapshot_sha256"] != board["source_snapshot_sha256"]:
        raise ValueError("stale E10 research board for E11.5")
    seats = {(s["ring"],s["slot"]):s for s in board["assigned_seats"]}
    by_id = {c["candidate_id"]:c for c in proposals["candidates"]}
    if len(by_id) != len(proposals["candidates"]):
        raise ValueError("duplicate E11.2 IDs")
    rows = recomputed["source_quality_flags"]
    if len(rows) > MAX_QUEUE_ITEMS:
        raise ValueError("E11.5 candidate count exceeds bounded review capacity")
    actionable, deferred = [], []
    for row in rows:
        cid = row["candidate_id"]
        if cid not in by_id:
            raise ValueError("E11.4 candidate missing from E11.2 proposals")
        proposal = by_id[cid]
        if (
            proposal["source"] != row["source"]
            or proposal["source_event_id"] != row["source_event_id"]
            or proposal["quote_sha256"] != row["quote_sha256"]
            or proposal["source_text_sha256"] != row["source_text_sha256"]
            or proposal["char_start"] != row["char_start"]
            or proposal["char_end"] != row["char_end"]
            or proposal["quote"] != row["quote"]
        ):
            raise ValueError("candidate lineage mismatch")
        label = row["kind"]
        if label not in ACTIONABLE and label not in DEFERRED:
            raise ValueError("unknown E11.4 quality category")
        parent = {
            "candidate_id":cid,
            "source":row["source"],
            "source_event_id":row["source_event_id"],
            "source_url":row["source_url"],
            "source_text_sha256":row["source_text_sha256"],
            "quote_sha256":row["quote_sha256"],
            "char_start":row["char_start"],
            "char_end":row["char_end"],
            "quote":row["quote"],
            "quality_category":label,
            "topic_for_review":proposal["topic_for_review"],
            "source_content_origin":row["content_origin"],
            "publisher_quote_authenticated":False,
            "scientific_result_verified":False,
            "review_performed":False,
        }
        if label in DEFERRED:
            deferred.append({
                **parent,"status":"deferred_non_evidence_context",
                "reason":row["next_check"],
                "verification_tasks":[]})
            continue
        seat_identity = proposal["proposed_reviewer"]
        seat = seats.get((seat_identity["ring"],seat_identity["slot"]))
        if seat is None or seat["member_id"] != seat_identity["member_id"]:
            raise ValueError("E11.2 specialist reviewer not in canonical Council72 catalog")
        # Distinguish the specialist's subject task from an independent
        # proposed provenance check. Neither is a completed council review.
        provenance = seats[(8,1)]
        tasks = [
            {
                "task":"topic_methodology_review",
                "member_id":seat["member_id"],
                "member_name":seat["member_name"],
                "ring":seat["ring"],"slot":seat["slot"],
                "status":"pending_no_agent_executed",
            },
            {
                "task":"independent_primary_source_provenance_check",
                "member_id":provenance["member_id"],
                "member_name":provenance["member_name"],
                "ring":provenance["ring"],"slot":provenance["slot"],
                "status":"pending_no_agent_executed",
            },
        ]
        actionable.append({
            **parent,
            "priority":ACTIONABLE[label],
            "status":"pending_original_publication_verification",
            "verification_questions":_verification_questions(
                row,proposal["topic_for_review"]),
            "verification_tasks":tasks,
        })
    actionable.sort(key=lambda r:(
        r["priority"],r["source"],r["char_start"],r["candidate_id"]))
    deferred.sort(key=lambda r:(
        r["source"],r["char_start"],r["candidate_id"]))
    if len(actionable)+len(deferred)!=len(rows):
        raise ValueError("E11.5 missing source context")
    result = {
        "kind":"klone-e11-5-primary-source-verification-queue",
        "schema_version":1,
        "source_event_ids":recomputed["source_event_ids"],
        "source_snapshot_sha256":board["source_snapshot_sha256"],
        "e11_4_report_sha256":recomputed["report_sha256"],
        "e11_3_ledger_sha256":recomputed["e11_3_ledger_sha256"],
        "e11_2_proposal_sha256":recomputed["e11_2_proposal_sha256"],
        "source_material_authenticated":False,
        "local_context_quotes":len(rows),
        "primary_source_checks_needed":len(actionable),
        "deferred_non_evidence_context_count":len(deferred),
        "pending_council_task_proposals":sum(
            len(row["verification_tasks"]) for row in actionable),
        "completed_council_reviews":0,
        "verified_scientific_results":0,
        "queue":actionable,
        "deferred":deferred,
        "next_step":"Get original authorized research texts, verify exact passages and study methods before claiming evidence.",
        "authority":{
            "memory_write":False,
            "external_network_actions":False,
            "private_room_access":False,
            "automatic_evidence_promotion":False,
            "scientific_truth_verified":False,
            "binding_council_votes":False,
            "owner_approval_to_fetch_sources":False,
        },
    }
    result["report_sha256"]=_fingerprint(result)
    return result

def main(argv=None):
    p = argparse.ArgumentParser(description="KLONE E11.5 offline research verification queue")
    p.add_argument("--klone-db",type=Path,required=True)
    for name in ("original","proposals","selected","ledger","quality"):
        p.add_argument("--"+name,type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args(argv)
    try:
        docs = [
            json_object(_read_input(
                getattr(args,name),MAX_MANIFEST_BYTES,
                "E11.5-"+name))
            for name in ("original","proposals","selected","ledger","quality")
        ]
        result=build_queue(args.klone_db,*docs)
        write_new_report(
            args.output.expanduser(),
            json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+"\n",
            Path.cwd().resolve(),
        )
    except (ValueError,PermissionError,OSError) as exc:
        p.error(str(exc))
    print(json.dumps({
        "kind":result["kind"],
        "checks":result["primary_source_checks_needed"],
        "deferred":result["deferred_non_evidence_context_count"],
        "task_proposals":result["pending_council_task_proposals"],
        "council_reviews_completed":0,
        "scientific_truth_verified":False,
        "memory_write":False,
        "output":str(args.output),
    },ensure_ascii=False))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
