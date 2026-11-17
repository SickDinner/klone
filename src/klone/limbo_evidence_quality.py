"""KLONE E11.4: fail-closed quality triage of existing approved E11.3 context.

This is *not* scientific validation. It distinguishes titles, questions,
editorial disclaimers and source-attributed claims in owner-supplied text.
It NEVER treats local summaries as authenticated primary publications.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .evidence_io import json_object, write_new_report
from .limbo_evidence_review import MAX_MANIFEST_BYTES, _read_input, review_manifest
from .limbo_council_workbench import _fingerprint
from .limbo_evidence_accept import accept_context

QUESTIONS=("mitä ","miksi ","miten ","kuinka ","voiko ","onko ","millo",
           "what ","why ","how ","is there ","does ","can ")
EDITORIAL=(
    "automaattinen arviointi", "ei todista", "ei tarkastettu",
    "tässä tiedostossa", "tässä selostuksessa",
    "tämä on tutkimuksen oma tulosväite",
    "ei ole vahvistettu", "tarkistettava", "not independently verified",
    "not authenticated", "not verified", "this summary",
    "cannot establish", "does not prove",
)
REPORTING=("tekijöiden mukaan", "tiivistelmän mukaan",
           "raportoidaan", "raportoitiin", "tekijöiden tiivistelmässä",
           "the authors report", "according to the authors",
           "reported ", "a study reports", "our results", "we report")
SUMMARY_TAGS=("selostus", "referaat", "tiivistelmä", "summary",
              "paraphrase", "ai-generated", "tekoäly", "ei varmennettu")


def _triage(quote, title):
    q=quote.strip()
    folded=q.casefold()
    title_key=title.casefold().strip().rstrip(" .")
    if folded.rstrip(" .")==title_key:
        return "publication_title_not_evidence"
    if q.endswith("?") or any(folded.startswith(x) for x in QUESTIONS):
        return "open_question_not_evidence"
    if any(phrase in folded for phrase in EDITORIAL):
        return "editorial_caution_not_evidence"
    if any(phrase in folded for phrase in REPORTING):
        return "attributed_research_claim_needs_primary_check"
    return "unverified_context_needs_primary_check"


def _next_step(label):
    if label=="publication_title_not_evidence":
        return "Keep as bibliographic heading; do not score as a research result."
    if label=="open_question_not_evidence":
        return "Keep in the question backlog; seek actual measurements and results."
    if label=="editorial_caution_not_evidence":
        return "Keep as safety/editorial metadata; do not score as a result."
    return ("Retrieve and inspect the actual publisher/arXiv full text, "
            "then compare exact quote, methods, population, endpoints and replication.")


def audit_quality(core_db, selected_manifest, prior_ledger,
                  original_manifest, proposal_report):
    if any(type(obj) is not dict for obj in (
        selected_manifest,prior_ledger,original_manifest,proposal_report
    )):
        raise ValueError("E11.2 and E11.3 source documents must be objects")
    selection=selected_manifest.get("e11_context_selection")
    if type(selection) is not dict or (
        selection.get("kind")!="klone-e11-3-owner-approved-context-only"
        or selection.get("selection_explicitly_authorized") is not True
        or selection.get("source_publication_authenticated") is not False
        or selection.get("scientific_truth_verified") is not False
        or selection.get("council_review_completed") is not False
        or selection.get("memory_write") is not False
    ):
        raise ValueError("missing or invalid E11.3 owner context-selection attestation")
    annotations=selected_manifest.get("annotations")
    ids=selection.get("selected_candidate_ids")
    if (type(annotations) is not list or not annotations or
        type(ids) is not list or len(ids)!=len(annotations) or
        any(type(i) is not str or len(i)!=20 for i in ids) or
        len(set(ids))!=len(ids)):
        raise ValueError("E11.3 accepted quote identity/count mismatch")
    for raw in annotations:
        if type(raw) is not dict or raw.get("stance")!="context":
            raise ValueError("E11.4 accepts owner-selected context only")
    # Reconstruct E11.3 from the ORIGINAL owner-supplied manifest and exact
    # E11.2 proposal file. The E11.3 owner-attestation field alone is not
    # evidence of a valid provenance chain. No memory writes or agent runs.
    replayed=accept_context(
        core_db,original_manifest,proposal_report,ids,
        owner_confirms_selection=True,
    )
    if replayed!=selected_manifest:
        raise ValueError("E11.3 selected manifest does not match original replay")
    regenerated=review_manifest(core_db,selected_manifest)
    if prior_ledger!=regenerated:
        raise ValueError("E11.3 ledger does not match current canonical source anchors")
    if (regenerated["annotation_count"]!=len(ids)
        or regenerated["council_state"]["completed_reviews"]!=0
        or regenerated["council_state"]["recorded_votes"]!=0
        or any(regenerated["authority"].values())):
        raise ValueError("E11.3 review crossed an authority boundary")
    sources=selected_manifest["sources"]
    context=[]
    counts={}
    for i, anchor in enumerate(regenerated["quote_anchors"]):
        role=anchor["source"]
        title=sources[role]["title"]
        q=anchor["quote"]
        label=_triage(q,title)
        counts[label]=counts.get(label,0)+1
        note=sources[role]["usage_rights_note"].casefold()
        declared_summary=any(tag in note for tag in SUMMARY_TAGS)
        context.append({
            "candidate_id":ids[i],
            "source":role,
            "source_event_id":anchor["source_event_id"],
            "source_url":sources[role]["source_url"],
            "source_text_sha256":anchor["source_text_sha256"],
            "quote_sha256":anchor["quote_sha256"],
            "char_start":anchor["char_start"],
            "char_end":anchor["char_end"],
            "quote":q,
            "kind":label,
            "content_origin":("owner_declared_summary_unverified" if declared_summary
                              else "owner_supplied_text_unverified"),
            "exact_match_in_supplied_text":True,
            "exact_match_in_original_publication":False,
            "valid_scientific_evidence":False,
            "reviewer_completed":False,
            "next_check":_next_step(label),
        })
    result={
        "kind":"klone-e11-4-context-quality-audit",
        "schema_version":1,
        "source_event_ids":regenerated["source_event_ids"],
        "source_snapshot_sha256":regenerated["source_snapshot_sha256"],
        "e11_3_ledger_sha256":regenerated["report_sha256"],
        "e11_2_proposal_sha256":selection["e11_2_report_sha256"],
        "owner_context_selected":True,
        "e11_2_e11_3_exact_replay_matches":True,
        "context_quote_count":len(context),
        "counts_by_kind":dict(sorted(counts.items())),
        "source_quality_flags":context,
        "scientifically_verified_quote_count":0,
        "independent_council_reviews":0,
        "council_votes":0,
        "primary_publication_authenticated":False,
        "scientific_truth_verified":False,
        "memory_write":False,
        "recommendation":"Do not promote local summaries to research evidence. Confirm original publications first.",
    }
    result["report_sha256"]=_fingerprint(result)
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description="KLONE E11.4 private read-only summary quality audit")
    p.add_argument("--klone-db",type=Path,required=True)
    p.add_argument("--original",type=Path,required=True)
    p.add_argument("--proposals",type=Path,required=True)
    p.add_argument("--selected",type=Path,required=True)
    p.add_argument("--ledger",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args(argv)
    try:
        data=audit_quality(
            args.klone_db,
            json_object(_read_input(args.selected,MAX_MANIFEST_BYTES,
                                    "E11.3-hyvaksytty manifesti")),
            json_object(_read_input(args.ledger,MAX_MANIFEST_BYTES,
                                    "E11.3-evidenssiraportti")),
            json_object(_read_input(args.original,MAX_MANIFEST_BYTES,
                                    "E11-alkuperainen manifesti")),
            json_object(_read_input(args.proposals,MAX_MANIFEST_BYTES,
                                    "E11.2-ehdotukset")),
        )
        write_new_report(args.output.expanduser(),
                         json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+"\n",
                         Path.cwd().resolve())
    except (ValueError,PermissionError,OSError) as exc:
        p.error(str(exc))
    print(json.dumps({
        "kind":data["kind"],
        "context_quotes":data["context_quote_count"],
        "triage":data["counts_by_kind"],
        "scientific_truth_verified":False,
        "memory_write":False,
        "output":str(args.output),
    },ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
