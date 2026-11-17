"""KLONE Atlas E6: transparent research synthesis from actual public Memory Core.

E6 proposes *questions and comparisons*, never certified facts. Claims,
headlines, and LLM-looking content are untrusted source data. All reads are
limited to research-room; there are no web requests or Memory Core writes.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import closing
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3

from .evidence_io import checked_path, write_new_report
from .guards import access_guard
from .limbo_atlas import BY_SOURCE, BY_DOMAIN, DOMAINS, _article_url, plan
from .limbo_memory_bridge import ROOM, EVENT_TYPE, _schema
from .council72 import catalog

MAX_SCAN = 10000
MAX_CANDIDATES = 48
MAX_LINKS = 18
STOP = frozenset("""about after again also among across against although and another are based been
between both can case could data does during each effects evidence from have into study
large more most new not observed other results report research that their these this those
through using were what when where which while with within without would jonka jossa kanssa
sekä myös ovat siitä tämä nämä tutkimus tutkimusjulkaisu article effects effect study
analysis approach method models model system results paper proposed new public claim""".split())

# Finnish queries are expanded to transparent English source-index terms.
# This is a controlled search synonym table, not a translation model.
FI_ALIASES = {
    "genetiikka": ("genetics","genetic","genome","genomics","dna","ancestry"),
    "genomi": ("genome","genomics","genetics"),
    "muinaisdna": ("ancient","dna","paleogenomics"),
    "evoluutio": ("evolution","evolutionary","population"),
    "psykologia": ("psychology","psychological","cognition"),
    "psykiatria": ("psychiatry","psychiatric","mental"),
    "farmakologia": ("pharmacology","drug","medicine","safety"),
    "neurotiede": ("neuroscience","neural","neuro","brain"),
    "filosofia": ("philosophy","ethics","ethical"),
    "geopolitiikka": ("world","international","geopolitics"),
    "talous": ("economics","economic","economy","finance","business"),
    "työllisyys": ("employment","labour","labor","jobs","workforce"),
    "tekoäly": ("artificial","intelligence","machine","learning","ai","llm"),
    "muisti": ("memory","remember","context","retrieval"),
    "ilmasto": ("climate","environment","earth"),
    "energia": ("energy","power","electricity"),
}

STRONG_NEG = ("no evidence", "not associated", "does not", "did not", "not significant",
              "no significant", "fails to", "lack of", "doesn't", "without evidence")
STRONG_POS = ("is associated", "significant increase", "significant decrease", "improves",
              "supports the", "demonstrates", "positive association", "was associated")


def _tokens(s: str) -> set[str]:
    if not isinstance(s,str):return set()
    return {x for x in re.findall(r"(?u)[^\W\d_][\w-]{2,}",s.casefold())
            if x not in STOP and len(x)<=35 and not x.startswith("http")}


def _selection(rows,query:str,limit:int) -> list[dict]:
    terms=_tokens(query)
    for term in tuple(terms):
        if term in FI_ALIASES:
            terms.update(FI_ALIASES[term])
    if not terms:raise ValueError("research question requires meaningful search terms")
    ranked=[]
    for doc in rows:
        title=_tokens(doc["title"])
        abstract=_tokens(doc["abstract"])
        tags=_tokens(doc["domain"].replace("_"," ")+" "+doc["source_id"].replace("-"," "))
        score=sum(6*(t in title)+3*(t in tags)+1*(t in abstract) for t in terms)
        if score:
            ranked.append((score,doc))
    ranked.sort(key=lambda x:(-x[0],x[1]["article_id"]))
    groups={domain.id:[] for domain in DOMAINS}
    for score,doc in ranked:
        groups[doc["domain"]].append((score,doc))
    selected=[]
    while len(selected)<limit and any(groups.values()):
        for domain in DOMAINS:
            if groups[domain.id] and len(selected)<limit:
                score,doc=groups[domain.id].pop(0)
                selected.append({**doc,"relevance_score":score})
    return selected


def _memories(db: str | Path) -> list[dict]:
    path=checked_path(Path(db).expanduser())
    if not path.is_file() or path.is_symlink():
        raise ValueError("existing regular KLONE Memory Core database required")
    if access_guard.evaluate(room_id=ROOM,actor_role="owner",
                             requested_permission="read").decision!="allowed":
        raise PermissionError("research-room is not readable by owner")
    with closing(sqlite3.connect(path.as_uri()+"?mode=ro",uri=True,timeout=15)) as conn:
        _schema(conn)
        # Never read a non-research-room row, regardless of metadata or input.
        cursor=conn.execute(
            "SELECT id,classification_level,title,evidence_text,metadata_json "
            "FROM memory_events WHERE room_id=? AND event_type=? AND status='active' "
            "ORDER BY id ASC LIMIT ?",(ROOM,EVENT_TYPE,MAX_SCAN+1))
        rows=cursor.fetchall()
    if len(rows)>MAX_SCAN:raise ValueError("memory read limit reached")
    latest={}
    counts=Counter()
    for event_id,classification,title,evidence,encoded in rows:
        if classification!="public":raise ValueError("non-public event in research-room")
        try:
            data=json.loads(encoded) if encoded else {}
        except (ValueError,TypeError) as exc:
            raise ValueError("invalid research memory metadata") from exc
        if (data.get("epistemic_status")!="unverified_publisher_claim"
            or data.get("truth_verified") is not False
            or not isinstance(data.get("article_id"),int)
            or not isinstance(data.get("version"),int)):
            raise ValueError("research event has unsupported epistemic status")
        source_id=data.get("source_id")
        source=BY_SOURCE.get(source_id)
        if (source is None or source.domain != data.get("domain")
            or BY_DOMAIN[source.domain].courier != data.get("courier_id")):
            raise ValueError("source/courier mismatch in research memory")
        url=_article_url(data.get("source_url"),source)
        label=str(title).replace("Julkinen lähdehavainto (vahvistamaton): ","",1)
        raw=str(evidence)
        if "Lähteen kuvaus: " not in raw or "\nAlkuperäinen julkaisu: " not in raw:
            raise ValueError("Memory Core research event has no source excerpt")
        abstract=raw.split("Lähteen kuvaus: ",1)[1].split("\nAlkuperäinen julkaisu: ",1)[0]
        doc={
            "event_id":event_id,"article_id":data["article_id"],
            "revision_id":data["revision_id"],"version":data["version"],
            "title":label,
            "abstract":abstract,
            "published_at":data.get("published_at"),
            "domain":source.domain,
            "source_id":source_id,"publisher_group":source.publisher,
            "courier_id":data["courier_id"],"source_url":url,
            "receipt_sha256":data.get("source_receipt_sha256"),
            "epistemic_status":"unverified_publisher_claim"
        }
        counts[doc["article_id"]]+=1
        old=latest.get(doc["article_id"])
        if old is None or (doc["version"],event_id)>(old["version"],old["event_id"]):
            latest[doc["article_id"]]=doc
    result=list(latest.values())
    result.sort(key=lambda x:x["article_id"])
    for doc in result:
        doc["version_count_in_core"]=counts[doc["article_id"]]
    return result


def _links(selected:list[dict]) -> list[dict]:
    candidates=[]
    for i,a in enumerate(selected):
        tokens_a=_tokens(a["title"]+" "+a["abstract"][:360])
        for b in selected[i+1:]:
            tokens_b=_tokens(b["title"]+" "+b["abstract"][:360])
            overlap=sorted(tokens_a&tokens_b)
            if len(overlap)<2:continue
            same_publisher=a["publisher_group"]==b["publisher_group"]
            negative_a=any(p in a["abstract"].casefold() for p in STRONG_NEG)
            negative_b=any(p in b["abstract"].casefold() for p in STRONG_NEG)
            positive_a=any(p in a["abstract"].casefold() for p in STRONG_POS)
            positive_b=any(p in b["abstract"].casefold() for p in STRONG_POS)
            cue=((negative_a and positive_b) or (negative_b and positive_a))
            # Linguistic cues are *not* a validated contradiction, and shared
            # technical words can match papers about different experiments.
            candidates.append({
                "kind":"potential_claim_tension" if cue else "topic_overlap",
                "first_event_id":a["event_id"],
                "second_event_id":b["event_id"],
                "shared_terms":overlap[:8],
                "shared_term_count":len(overlap),
                "different_publishers":not same_publisher,
                "independent_evidence_verified":False,
                "contradiction_verified":False,
                "explanation":(
                    "Vastakkaisiin suuntiin viittaavia ilmauksia: tarkista tutkimuskysymys, "
                    "mittarit, aineistot ja negation kohde alkuperäislähteistä."
                    if cue else
                    "Yhteinen aihepiiri: vertaa tutkimuskysymyksiä ja menetelmiä. "
                    "Samankaltaiset sanat eivät osoita samaa tulosta."
                ),
            })
    candidates.sort(key=lambda v:(0 if v["kind"]=="potential_claim_tension" else 1,
                                   -v["shared_term_count"],v["first_event_id"],
                                   v["second_event_id"]))
    return candidates[:MAX_LINKS]


def analyze(db: str | Path, question: str, *, limit: int=24,
            target_ring:int|None=None) -> dict:
    if not isinstance(question,str) or not 3<=len(question.strip())<=160:
        raise ValueError("research question must be 3..160 chars")
    if type(limit) is not int or not 1<=limit<=MAX_CANDIDATES:
        raise ValueError("limit must be integer 1..48")
    if target_ring is not None and (type(target_ring) is not int or
                                    not 2<=target_ring<=8):
        raise ValueError("ring must be an integer 2..8")
    candidates=_memories(db)
    selected=_selection(candidates,question,limit)
    links=_links(selected)
    by_domain=Counter(d["domain"] for d in selected)
    roster=catalog()
    questions=[]
    for domain in DOMAINS:
        group=[x for x in selected if x["domain"]==domain.id]
        if not group:continue
        ring_id=target_ring or domain.preferred_ring
        ring=roster["rings"][ring_id-1]
        # Responsible courier and actual specialist members are retained
        # as identifiable *suggestion owners*, with no invented agent run.
        member_ids=[m["id"] for m in roster["members"] if m["ring"]==ring_id]
        suggestions=[
            "Vertaa " + str(len(group)) + " havaintoa alkuperäislähteisiin: "
            "mitkä mittarit ja otokset ovat oikeasti vertailukelpoisia?",
            "Esitä vaihtoehtoinen selitysmalli ja siitä mitattava, kumottavissa oleva ennuste.",
            "Etsi riippumaton vastatutkimus ja tarkista julkaisun vertaisarviointitila.",
        ]
        questions.append({
            "domain":domain.id,"agent_id":domain.courier,
            "specialist_ring":ring_id,"ring_name":ring["dante_label"],
            "specialist_member_ids":member_ids,
            "paper_event_ids":[x["event_id"] for x in group],
            "research_prompt":domain.research_question,
            "proposed_questions":suggestions,
            "state":"not_executed_research_proposal",
        })
    council_preview=None
    if selected:
        from .limbo_atlas import validate_records
        source_records=[]
        for entry in selected:
            source_records.append({
                "source_id":entry["source_id"],
                "courier_id":entry["courier_id"],
                "url":entry["source_url"],
                "title":entry["title"],
                "summary":entry["abstract"],
                "published_at":entry["published_at"],
            })
        # Re-run the exact existing 72-seat governance machinery on this
        # source-scoped, explicitly unverified memory selection. No execution.
        validated=validate_records(source_records)
        for record,entry in zip(validated,selected):
            if record["receipt_sha256"]!=entry["receipt_sha256"]:
                raise ValueError("Memory Core observation differs from stored E3 receipt")
        council_preview=plan(source_records,ring_id=target_ring,question=question)
    digest=sha256(json.dumps(
        [question,target_ring,[(d["event_id"],d["receipt_sha256"]) for d in selected]],
        ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    return {
        "kind":"klone-atlas-e6-research-intelligence",
        "schema_version":1,
        "question":question,
        "snapshot_sha256":digest,
        "public_research_memory_count":len(candidates),
        "matched_memory_count":len(selected),
        "domain_counts":dict(sorted(by_domain.items())),
        "source_groups":sorted({d["publisher_group"] for d in selected}),
        "memories":[{
            k:d[k] for k in ("event_id","article_id","version",
                             "version_count_in_core","domain","source_id",
                             "courier_id","publisher_group","title","source_url",
                             "epistemic_status","relevance_score")
        } for d in selected],
        "comparisons":links,"research_drafts":questions,
        "council72_preview":council_preview,
        "limits":[
            "Only public research-room memory events are read.",
            "Matching and contradiction flags are lexical hypotheses, not verified scientific conclusions.",
            "No article full text, methods, independent replication or peer review was verified.",
            "No specialist agent actually executed a research project or autonomously endorsed a claim.",
        ],
        "authority":{"network_fetch":False,"memory_write":False,
                     "private_memory_access":False,"external_posting":False,
                     "automatic_approval":False,"human_review_required":True},
    }


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description="Offline research intelligence over public KLONE Memory Core")
    parser.add_argument("--klone-db",required=True,type=Path)
    parser.add_argument("--question",required=True)
    parser.add_argument("--limit",type=int,default=24)
    parser.add_argument("--ring",type=int)
    parser.add_argument("--output",required=True,type=Path)
    args=parser.parse_args(argv)
    result=analyze(args.klone_db,args.question,limit=args.limit,target_ring=args.ring)
    payload=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+"\n"
    write_new_report(args.output.expanduser(),payload,Path.cwd().resolve())
    print(json.dumps({"output":str(args.output),"matched":result["matched_memory_count"],
                      "comparisons":len(result["comparisons"]),
                      "drafts":len(result["research_drafts"]),
                      "snapshot_sha256":result["snapshot_sha256"]},
                     ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
