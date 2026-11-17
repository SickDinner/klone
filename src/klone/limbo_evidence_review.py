"""E11: owner-supplied, source-bound, OFFLINE evidence review.

No network fetching, LLM inference, source-truth claims, votes or Memory Core
mutation. A quote is retained only if it appears exactly once in the text
the owner explicitly supplied for an actual canonical E9.1 public source.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import re

from .evidence_io import EvidenceIOError,json_object,read_bounded,write_new_report
from .limbo_council_workbench import council_review, _fingerprint

MAX_MANIFEST_BYTES=256*1024
MAX_TEXT_CHARS=60000
MAX_ANNOTATIONS=40
CLAIM_KEY=re.compile(r"^[a-z][a-z0-9_-]{1,63}$")
STANCES={"support_candidate","counter_candidate","context"}


def _source_info(source):
    return {
        "event_id":source["event_id"],
        "source_url":source["source_url"],
        "receipt_sha256":source["receipt_sha256"],
        "title":source["title"],
        "source_class":source["source_class"],
        "version":source["version"],
        "text":"",
        "owner_supplied":False,
        "usage_rights_note":"",
    }


def prepare(core_db,first_event_id,second_event_id,*,question="genetiikka"):
    board=council_review(core_db,first_event_id,second_event_id,question=question)
    return {
        "kind":"klone-e11-owner-evidence-template",
        "schema_version":1,"question":question,
        "source_snapshot_sha256":board["source_snapshot_sha256"],
        "sources":{"A":_source_info(board["source_summary"]["source_a"]),
                   "B":_source_info(board["source_summary"]["source_b"])},
        "annotations":[],
        "instructions":{
            "step_1":"Paste only text you are allowed to use into A/B text and state its usage rights.",
            "step_2":"Set owner_supplied=true for each excerpt you intentionally provide.",
            "step_3":"Annotate exact, unique quotes, claim_key, stance and note in annotations.",
            "step_4":"Run offline --review; quotes are exact matches, not automatically interpreted facts.",
        },
        "authority":{"memory_write":False,"external_network_actions":False,
                     "scientific_truth_verified":False,"council_votes":False},
    }


def _source_check(incoming,expected,letter):
    if type(incoming) is not dict:
        raise ValueError(f"source {letter} must be a JSON object")
    for key in ("event_id","source_url","receipt_sha256",
                "title","source_class","version"):
        if incoming.get(key)!=expected[key] or type(incoming.get(key))!=type(expected[key]):
            raise ValueError(f"source {letter} provenance mismatch: {key}")
    if incoming.get("owner_supplied") is not True:
        raise ValueError(f"source {letter} needs explicit owner-supplied attestation")
    note=incoming.get("usage_rights_note")
    if type(note) is not str or not 5<=len(note)<=240:
        raise ValueError(f"source {letter} needs a bounded usage-rights note")
    text=incoming.get("text")
    if type(text) is not str or not 30<=len(text)<=MAX_TEXT_CHARS:
        raise ValueError(f"source {letter} text must be 30..{MAX_TEXT_CHARS} characters")
    if "\x00" in text:
        raise ValueError("source text contains NUL")
    return text


def _position(text,quote):
    if text.count(quote)!=1:
        raise ValueError("annotated quote must occur exactly once in supplied source text")
    i=text.index(quote)
    return i,i+len(quote)


def _annotation(raw,texts,source_ids):
    if type(raw) is not dict:
        raise ValueError("annotation must be an object")
    if set(raw)!={"source","claim_key","quote","stance","note"}:
        raise ValueError("annotation keys must be source, claim_key, quote, stance, note")
    role=raw["source"]
    if type(role) is not str or role not in texts:
        raise ValueError("unknown annotation source")
    key=raw["claim_key"]
    if type(key) is not str or not CLAIM_KEY.fullmatch(key):
        raise ValueError("invalid claim key")
    stance=raw["stance"]
    if type(stance) is not str or stance not in STANCES:
        raise ValueError("invalid evidence stance")
    quote=raw["quote"]
    if type(quote) is not str or not 12<=len(quote)<=400 or not quote.strip():
        raise ValueError("quote must be 12..400 visible characters")
    note=raw["note"]
    if type(note) is not str or not 3<=len(note)<=400:
        raise ValueError("annotation note must be 3..400 characters")
    start,end=_position(texts[role],quote)
    return {"source":role,"source_event_id":source_ids[role],
            "claim_key":key,"quote":quote,"quote_sha256":sha256(quote.encode()).hexdigest(),
            "offset_type":"unicode_character","char_start":start,"char_end":end,
            "source_text_sha256":sha256(texts[role].encode()).hexdigest(),
            "stance":stance,"stance_is_owner_annotation":True,
            "independently_verified":False,"note":note}


def review_manifest(core_db,manifest):
    if (type(manifest) is not dict or
            type(manifest.get("schema_version")) is not int or
            manifest.get("schema_version")!=1):
        raise ValueError("E11 schema v1 object required")
    if manifest.get("kind")!="klone-e11-owner-evidence-template":
        raise ValueError("invalid E11 manifest kind")
    question=manifest.get("question")
    if type(question) is not str or not 3<=len(question)<=160:
        raise ValueError("invalid question")
    sources=manifest.get("sources")
    if type(sources) is not dict or set(sources)!={"A","B"}:
        raise ValueError("two explicit source slots A and B required")
    a=sources["A"]
    b=sources["B"]
    if type(a) is not dict or type(b) is not dict:
        raise ValueError("invalid source slots")
    # Re-evaluate the actual currently approved canonical E9.1 publication
    # pair; a stale event, newly rejected pair or altered receipt fails closed.
    board=council_review(core_db,a.get("event_id"),b.get("event_id"),question=question)
    if manifest.get("source_snapshot_sha256")!=board["source_snapshot_sha256"]:
        raise ValueError("source snapshot became stale")
    originals=board["source_summary"]
    texts={role:_source_check(sources[role],originals[f"source_{role.lower()}"],role)
           for role in ("A","B")}
    annotations=manifest.get("annotations")
    if type(annotations) is not list or len(annotations)>MAX_ANNOTATIONS:
        raise ValueError("annotation list limit exceeded")
    source_ids={r:sources[r]["event_id"] for r in ("A","B")}
    anchors=[_annotation(x,texts,source_ids) for x in annotations]
    signatures=[(x["source"],x["claim_key"],x["char_start"],x["char_end"],
                 x["stance"]) for x in anchors]
    if len(signatures)!=len(set(signatures)):
        raise ValueError("duplicate annotation")
    grouped={}
    for item in anchors:
        grouped.setdefault(item["claim_key"],[]).append(item)
    opposing=[]
    for key,items in sorted(grouped.items()):
        support={x["source_event_id"] for x in items
                 if x["stance"]=="support_candidate"}
        counter={x["source_event_id"] for x in items
                 if x["stance"]=="counter_candidate"}
        if support and counter:
            opposing.append({"claim_key":key,
                "support_event_ids":sorted(support),
                "counter_event_ids":sorted(counter),
                "status":"opposing_owner_annotations_not_verified_contradiction"})
    state="unreviewed_no_annotations" if not anchors else "owner_annotated_not_verified"
    report={
        "kind":"klone-e11-offline-evidence-ledger",
        "schema_version":1,"question":question,
        "source_snapshot_sha256":board["source_snapshot_sha256"],
        "council72_catalog_sha256":board["catalog_sha256"],
        "source_event_ids":[source_ids["A"],source_ids["B"]],
        "source_content":{
            r:{"event_id":source_ids[r],
               "text_sha256":sha256(texts[r].encode()).hexdigest(),
               "characters":len(texts[r]),
               "usage_rights_note":sources[r]["usage_rights_note"],
               "content_provenance":"owner_supplied_unverified",
               "full_publication_verified":False}
            for r in ("A","B")},
        "quote_anchors":anchors,
        "annotation_count":len(anchors),
        "opposing_annotation_candidates":opposing,
        "epistemic_state":state,
        "open_checks":["Was each supplied excerpt copied faithfully from the linked primary source?",
                       "Are A and B independent publications and independent datasets?",
                       "Do measured endpoints, populations and study methods actually match?",
                       "Have negative findings, conflicts, corrections and replications been checked?",
                       "Does the exact quote support the owner's stated interpretation?"],
        "council_state":{"open_seat_tasks":72,"completed_reviews":0,
                         "recorded_votes":0,"approval":False},
        "authority":{"memory_write":False,"network_access":False,
                     "private_room_read":False,"binding_decisions":False,
                     "scientific_truth_verified":False},
    }
    report["report_sha256"]=_fingerprint(report)
    return report



def fill_template(core_db,template,source_a_bytes,source_b_bytes,
                  *,rights_note_a,rights_note_b):
    """Intentional local-text intake; validation uses original canonical sources.

    This does not assume that a user's pasted excerpt is an authentic paper.
    Never stores any supplied text in the original KLONE Memory Core.
    """
    if type(template) is not dict or template.get("kind")!="klone-e11-owner-evidence-template":
        raise ValueError("an actual E11 source manifest template is required")
    if type(source_a_bytes) is not bytes or type(source_b_bytes) is not bytes:
        raise ValueError("text files must be supplied as bytes")
    result=deepcopy(template)
    for role,raw,note in (("A",source_a_bytes,rights_note_a),
                          ("B",source_b_bytes,rights_note_b)):
        if type(note) is not str or not 5<=len(note)<=240:
            raise ValueError("owner must provide rights notes for both texts")
        if len(raw)>MAX_TEXT_CHARS*4:
            raise ValueError("owner-supplied source text is oversized")
        try:
            txt=raw.decode("utf-8")
        except UnicodeError as error:
            raise ValueError("source text is not UTF-8") from error
        source=result.get("sources",{}).get(role)
        if type(source) is not dict:
            raise ValueError("E11 source slot missing")
        source["text"]=txt
        source["usage_rights_note"]=note
        source["owner_supplied"]=True
    # E11 validates canonical pair, all source identity fields, current
    # receipt hashes, rights flags and limits before any manifest is saved.
    review_manifest(core_db,result)
    return result

def _read_input(path: Path, limit: int, label: str) -> bytes:
    """Make a missing/unsafe owner input unambiguous without weakening I/O guards."""
    try:
        return read_bounded(path,limit)
    except EvidenceIOError as exc:
        raise ValueError(f"{label}: {exc.code}: {path}") from exc


def main(argv=None):
    p=argparse.ArgumentParser(description="KLONE E11 offline quoted evidence ledger")
    p.add_argument("--klone-db",type=Path,required=True)
    choice=p.add_mutually_exclusive_group(required=True)
    choice.add_argument("--prepare",type=int,nargs=2,metavar=("FIRST","SECOND"))
    choice.add_argument("--review",type=Path,metavar="OWNER_MANIFEST")
    choice.add_argument("--fill",type=Path,metavar="TEMPLATE")
    p.add_argument("--source-a-file",type=Path)
    p.add_argument("--source-b-file",type=Path)
    p.add_argument("--rights-note-a")
    p.add_argument("--rights-note-b")
    p.add_argument("--owner-confirms-supplied-text",action="store_true")
    p.add_argument("--question",default="genetiikka")
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args(argv)
    try:
        if args.prepare:
            data=prepare(args.klone_db,*args.prepare,question=args.question)
        elif args.fill:
            if (not args.owner_confirms_supplied_text or
                args.source_a_file is None or args.source_b_file is None):
                raise ValueError("fill requires two local files and explicit owner confirmation")
            data=fill_template(
                args.klone_db,
                json_object(_read_input(args.fill,MAX_MANIFEST_BYTES,"E11-pohjatiedosto")),
                _read_input(args.source_a_file,MAX_TEXT_CHARS*4,"Lahdeteksti A"),
                _read_input(args.source_b_file,MAX_TEXT_CHARS*4,"Lahdeteksti B"),
                rights_note_a=args.rights_note_a,
                rights_note_b=args.rights_note_b)
        else:
            data=review_manifest(args.klone_db,
                                 json_object(_read_input(args.review,MAX_MANIFEST_BYTES,"E11-tarkistettava manifesti")))
        write_new_report(args.output.expanduser(),
                         json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+"\n",
                         Path.cwd().resolve())
    except (OSError,ValueError,PermissionError) as exc:
        p.error(str(exc))
    print(json.dumps({"kind":data["kind"],
                      "quotes":data.get("annotation_count",0),
                      "memory_write":False,"output":str(args.output)},
                     ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
