"""KLONE E11.3: consent-gated *context-only* quote selection.

Recompute E11.2 proposals from the unchanged owner manifest before accepting
their IDs. No support/counter assertions, journal mutation, model review or
Council72 votes. A selected quote is not proof of publisher authenticity.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path

from .evidence_io import json_object,write_new_report
from .limbo_evidence_candidates import suggest
from .limbo_evidence_review import MAX_MANIFEST_BYTES,_read_input,review_manifest
from .limbo_council_workbench import _fingerprint


def accept_context(core_db,manifest,proposals,selected_ids,
                   *,owner_confirms_selection=False):
    if owner_confirms_selection is not True:
        raise ValueError("owner must explicitly approve selected context quotes")
    if type(manifest) is not dict or type(proposals) is not dict:
        raise ValueError("manifest and suggestions must be JSON objects")
    if manifest.get("annotations")!=[]:
        raise ValueError("only an unannotated E11 manifest can receive new context suggestions")
    limit=proposals.get("per_source_limit")
    # Recompute the entire candidate set from Memory Core + the supplied
    # manifest. This catches forged reviewer IDs, changed source text, stale
    # receipt hashes, or fabricated quote locations in proposal JSON.
    expected=suggest(core_db,manifest,per_source_limit=limit)
    if proposals!=expected or proposals.get("report_sha256")!=_fingerprint({
        k:v for k,v in proposals.items() if k!="report_sha256"
    }):
        raise ValueError("stale or altered E11.2 proposal report")
    if (type(selected_ids) is not list or not selected_ids
        or len(selected_ids)>len(expected["candidates"])
        or any(type(s) is not str for s in selected_ids)
        or len(set(selected_ids))!=len(selected_ids)):
        raise ValueError("selected candidate IDs must be distinct and nonempty")
    available={x["candidate_id"]:x for x in expected["candidates"]}
    if any(s not in available for s in selected_ids):
        raise ValueError("unknown candidate ID: proposal report cannot be trusted")
    output=deepcopy(manifest)
    # Keep the source text itself exactly as the owner originally supplied it;
    # all accepted stances are context and no model inference is recorded.
    output["annotations"]=[{
        "source":available[cid]["source"],
        "claim_key":"context-"+available[cid]["source"].lower()+"-"+cid[:12],
        "quote":available[cid]["quote"],
        "stance":"context",
        "note":"Owner selected unverified context from provided text; not an authenticated publication quote.",
    } for cid in selected_ids]
    output["e11_context_selection"]={
        "kind":"klone-e11-3-owner-approved-context-only",
        "e11_2_report_sha256":proposals["report_sha256"],
        "selected_candidate_ids":list(selected_ids),
        "selection_explicitly_authorized":True,
        "source_publication_authenticated":False,
        "scientific_truth_verified":False,
        "council_review_completed":False,
        "memory_write":False,
    }
    result=review_manifest(core_db,output)
    if result["annotation_count"]!=len(selected_ids):
        raise ValueError("selected quotes were not anchored as expected")
    if result["epistemic_state"]!="owner_annotated_not_verified":
        raise ValueError("selected quotes were incorrectly promoted")
    return output


def main(argv=None):
    p=argparse.ArgumentParser(
        description="KLONE E11.3 owner-confirmed context annotation, no true/false claims"
    )
    p.add_argument("--klone-db",type=Path,required=True)
    p.add_argument("--manifest",type=Path,required=True)
    p.add_argument("--proposals",type=Path,required=True)
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument("--all-context",action="store_true")
    group.add_argument("--candidate-id",action="append")
    p.add_argument("--owner-confirms-candidate-selection",action="store_true")
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args(argv)
    try:
        manifest=json_object(_read_input(
            args.manifest,MAX_MANIFEST_BYTES,"E11-manifesti"))
        proposals=json_object(_read_input(
            args.proposals,MAX_MANIFEST_BYTES,"E11.2-ehdotusraportti"))
        ids=([x["candidate_id"] for x in proposals.get("candidates",[])]
             if args.all_context else args.candidate_id)
        selected=accept_context(
            args.klone_db,manifest,proposals,ids,
            owner_confirms_selection=args.owner_confirms_candidate_selection)
        write_new_report(args.output.expanduser(),
                         json.dumps(selected,ensure_ascii=False,indent=2,allow_nan=False)+"\n",
                         Path.cwd().resolve())
    except (ValueError,PermissionError,OSError) as error:
        p.error(str(error))
    print(json.dumps({
        "kind":"klone-e11-3-owner-approved-context-only",
        "selected_context_quotes":len(ids),
        "scientific_truth_verified":False,
        "council_completed_reviews":0,"memory_write":False,
        "output":str(args.output),
    },ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
