"""Atlas E8: epistemic radar, source dependency warnings and research time-machine.

Read-only deterministic discovery aids. This is an *attention allocator*:
scores measure what should be investigated, not truth probabilities.
No autonomous experiments, network reads, memory writes or approvals.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from .evidence_io import json_object,read_bounded,write_new_report
from .limbo_atlas import DOMAINS
from .limbo_intelligence import _memories,_tokens,FI_ALIASES

MAX_MATCH=96
MAX_PAIRS=24
MAX_SNAPSHOT_BYTES=12*1024*1024

LENSES=(
    ("null_model","Mikä on yksinkertaisin nollahypoteesi, joka selittää havainnon?"),
    ("confounding","Mitkä tuntemattomat muuttujat voisivat selittää saman korrelaation?"),
    ("measurement","Voiko mittausvirhe, otoskoko tai valikointi luoda näennäisen tuloksen?"),
    ("reverse_causality","Voisiko syy-seuraussuhteen suunta olla päinvastainen?"),
    ("source_dependence","Perustuvatko julkaisut samaan dataan, preprinttiin tai tiedotteeseen?"),
    ("boundary_conditions","Missä populaatiossa, ajassa tai olosuhteissa selitys lakkaa toimimasta?"),
    ("counterexample","Millainen riippumaton havainto kumoaisi hypoteesin?"),
    ("safety_ethics","Mitä haittoja syntyy, jos vahvistamaton havainto otetaan käyttöön?"),
)


def _hash(obj)->str:
    return sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True,
           separators=(",",":"),allow_nan=False).encode()).hexdigest()


def _query_terms(query):
    if not isinstance(query,str) or not 3<=len(query.strip())<=160:
        raise ValueError("research question must contain 3..160 characters")
    terms=_tokens(query)
    for x in tuple(terms):
        terms.update(FI_ALIASES.get(x,()))
    if not terms:raise ValueError("no useful search terms")
    return terms


def _expand_across_domains(all_docs, seeds):
    """Look beyond query-matched domains without inventing evidence links.

    A potential bridge needs >=2 corpus-distinctive shared terms, including
    one from a publication title. Single-term matches are only weak leads.
    All candidates retain actual Memory Core event IDs and source URLs.
    """
    if not seeds:
        return [], [], 0, {}
    seed_domains={d["domain"] for d in seeds}
    outside=[d for d in all_docs if d["domain"] not in seed_domains]
    if not outside:
        return [], [], 0, {}
    frequencies=Counter()
    for doc in all_docs:
        frequencies.update(_tokens(doc["title"]+" "+doc["abstract"][:400]))
    cap=max(3,len(all_docs)//3)
    def distinctive(doc):
        return {t for t in _tokens(doc["title"]+" "+doc["abstract"][:400])
                if frequencies[t]<=cap and len(t)>=4}
    seed_terms={d["event_id"]:distinctive(d) for d in seeds}
    outside_terms={d["event_id"]:distinctive(d) for d in outside}
    pairs=[]
    weak=[]
    for seed in seeds:
        for other in outside:
            common=sorted(seed_terms[seed["event_id"]] &
                          outside_terms[other["event_id"]])
            in_title=sorted(set(common)&
                            (_tokens(seed["title"])|_tokens(other["title"])))
            if not common or not in_title:
                continue
            pair={
                "first_event_id":seed["event_id"],
                "second_event_id":other["event_id"],
                "first_source_url":seed["source_url"],
                "second_source_url":other["source_url"],
                "domains":sorted([seed["domain"],other["domain"]]),
                "shared_terms":common[:8],
                "shared_term_count":len(common),
                "candidate_origin":"other_domain_public_memory",
                "different_publisher_groups":
                    seed["publisher_group"]!=other["publisher_group"],
                "independent_studies_confirmed":False,
                "cross_domain_hypothesis_verified":False,
                "next_experiment":"Tarkista molemmat alkuperäiset julkaisut ja "
                                  "määritä yhteinen testattava muuttuja sekä "
                                  "itsenäinen kumoava havainto.",
            }
            if len(common)>=2:
                pair["candidate_priority"]=min(8,len(common))*3+(
                    2 if pair["different_publisher_groups"] else 0)
                pairs.append(pair)
            else:
                pair["candidate_priority"]=0
                pair["status"]="weak_single_term_lead_not_confirmed"
                weak.append(pair)
    pairs.sort(key=lambda p:(-p["candidate_priority"],
                 p["first_event_id"],p["second_event_id"]))
    weak.sort(key=lambda p:(p["first_event_id"],p["second_event_id"]))
    bridges={}
    for pair in pairs[:MAX_PAIRS]:
        second=next(d for d in outside if d["event_id"]==pair["second_event_id"])
        bridges[second["event_id"]]={
            "event_id":second["event_id"],"domain":second["domain"],
            "source_url":second["source_url"],"title":second["title"],
            "source_id":second["source_id"],
            "epistemic_status":"unverified_publisher_claim",
        }
    return pairs[:MAX_PAIRS],weak[:8],len(outside),bridges


def radar(core_db,query,*,limit=48):
    if type(limit) is not int or not 2<=limit<=MAX_MATCH:
        raise ValueError("limit must be 2..96")
    terms=_query_terms(query)
    docs=_memories(core_db)
    relevant=[]
    for d in docs:
        title=_tokens(d["title"])
        abstract=_tokens(d["abstract"])
        tags=_tokens(d["domain"]+" "+d["source_id"])
        score=sum(4*(x in title)+2*(x in tags)+int(x in abstract) for x in terms)
        if score:
            relevant.append({**d,"relevance":score})
    relevant.sort(key=lambda d:(-d["relevance"],d["article_id"]))
    # Round robin disciplines: a single high-volume field must not crowd out
    # cross-disciplinary leads, while the cap bounds quadratic comparisons.
    pool={d.id:[] for d in DOMAINS}
    for d in relevant:pool[d["domain"]].append(d)
    chosen=[]
    while len(chosen)<limit and any(pool.values()):
        for d in DOMAINS:
            if pool[d.id] and len(chosen)<limit:chosen.append(pool[d.id].pop(0))
    pairs=[]
    for i,a in enumerate(chosen):
        ta=_tokens(a["title"]+" "+a["abstract"][:400])
        for b in chosen[i+1:]:
            if a["domain"]==b["domain"]:continue
            overlap=sorted(ta&_tokens(b["title"]+" "+b["abstract"][:400]))
            if len(overlap)<2:continue
            same_publisher=a["publisher_group"]==b["publisher_group"]
            # Investigation priority, NEVER an evidence reliability score.
            score=min(8,len(overlap))*3+int(not same_publisher)*2+int(
                 a["version_count_in_core"]>1 or b["version_count_in_core"]>1)
            pairs.append({
                "first_event_id":a["event_id"],"second_event_id":b["event_id"],
                "domains":sorted([a["domain"],b["domain"]]),
                "shared_terms":overlap[:8],
                "candidate_priority":score,
                "different_publisher_groups":not same_publisher,
                "independent_studies_confirmed":False,
                "cross_domain_hypothesis_verified":False,
                "next_experiment":"Määritä yhteinen mitattava muuttuja, vaihtoehtoinen "
                                  "selitys ja riippumaton vastatesti.",
            })
    pairs.sort(key=lambda d:(-d["candidate_priority"],
             d["first_event_id"],d["second_event_id"]))
    matched_domains=sorted({d["domain"] for d in chosen})
    bridge_mode=len(matched_domains)==1
    bridged_pairs=[]
    weak_leads=[]
    outside_examined=0
    bridge_sources={}
    if bridge_mode:
        bridged_pairs,weak_leads,outside_examined,bridge_sources=(
            _expand_across_domains(docs,chosen))
        pairs=(pairs+bridged_pairs)[:MAX_PAIRS]
    proposals=[]
    domains=Counter(x["domain"] for x in chosen)
    for domain in DOMAINS:
        n=domains.get(domain.id,0)
        if not n:continue
        related=[x for x in pairs if domain.id in x["domains"]]
        # Attention score allocates human review, not truth.
        debt=4+int(not related)*3+int(n==1)*2
        proposals.append({
            "domain":domain.id,"courier_id":domain.courier,
            "preferred_ring":domain.preferred_ring,
            "papers_in_selection":n,
            "cross_domain_candidates":len(related),
            "attention_priority":debt,
            "epistemic_debt":[
                "Check the original complete publications and underlying methods.",
                "Independently reproduce or locate the original datasets.",
                "Search for falsifying observations and negative results.",
                "Verify whether different sources reuse the same evidence.",
            ],
            "status":"owner_review_needed",
        })
    proposals.sort(key=lambda d:(-d["attention_priority"],d["domain"]))
    return {
        "kind":"klone-atlas-e8-discovery-radar","schema_version":1,
        "query":query,"available_public_memories":len(docs),
        "matched":len(relevant),"selected":len(chosen),
        "snapshot_sha256":_hash([(d["event_id"],d["receipt_sha256"]) for d in chosen]),
        "discipline_coverage":dict(sorted(domains.items())),
        "cross_discipline_candidates":pairs[:MAX_PAIRS],
        "bridge_mode":"cross_domain_expansion" if bridge_mode else "query_domains",
        "bridge_documents":sorted(bridge_sources.values(),key=lambda d:d["event_id"]),
        "bridge_document_count":len(bridge_sources),
        "outside_domain_documents_examined":outside_examined,
        "weak_single_term_leads":weak_leads,
        "diagnostics":{
            "matched_domain_count":len(matched_domains),
            "query_selected_domains":matched_domains,
            "minimum_distinctive_terms_for_expansion":2,
            "cross_domain_pairs_found":len(pairs),
            "why_no_pairs":(
                "No query-matched publications were available."
                if not chosen else
                "All selected publications belong to one domain and the corpus has no other domains."
                if bridge_mode and outside_examined==0 else
                "Other-domain publications were examined, but no pair met the two-distinctive-term title-overlap criterion."
                if bridge_mode and not pairs else
                "No query-selected pair met the two-term topic-overlap criterion."
                if not pairs else None
            ),
            "suggested_next_queries":(
                [query+" neuroscience",query+" ethics",query+" economics"]
                if bridge_mode and not pairs else []
            ),
            "no_links_does_not_mean_no_scientific_relation":True,
        },
        "attention_queue":proposals,
        "adversarial_research_lenses":[{"id":name,"question":prompt} for name,prompt in LENSES],
        "authority":{"writes_memory":False,"reads_private_data":False,
                     "posts_external":False,"autonomous_action":False,
                     "automatic_truth_upgrade":False},
        "scoring_interpretation":"review priority only; not truth, causality, confidence or study independence",
    }


def compare_snapshots(old,new):
    """Time machine over two actual saved E6 analysis reports."""
    for doc in (old,new):
        if not isinstance(doc,dict) or doc.get("kind")!="klone-atlas-e6-research-intelligence":
            raise ValueError("both inputs must be Atlas E6 analysis exports")
        if not isinstance(doc.get("memories"),list) or len(doc["memories"])>48:
            raise ValueError("invalid E6 snapshot memories")
        if doc.get("question")!=old.get("question"):
            raise ValueError("snapshots must have the same research question")
    def index(rows):
        out={}
        for r in rows:
            if not isinstance(r,dict) or type(r.get("article_id")) is not int or (
                    type(r.get("version")) is not int or
                    type(r.get("event_id")) is not int):
                raise ValueError("invalid snapshot entry")
            if r["article_id"] in out:raise ValueError("duplicate article")
            out[r["article_id"]]=r
        return out
    a=index(old["memories"]);b=index(new["memories"])
    added=sorted(set(b)-set(a))
    absent=sorted(set(a)-set(b))
    changed=sorted(i for i in set(a)&set(b) if a[i]["version"]!=b[i]["version"])
    return {
        "kind":"klone-atlas-e8-memory-time-machine",
        "schema_version":1,"question":old["question"],
        "before_snapshot":old.get("snapshot_sha256"),
        "after_snapshot":new.get("snapshot_sha256"),
        "new_in_selection":[{"article_id":i,"event_id":b[i]["event_id"],
                             "source_url":b[i].get("source_url")} for i in added],
        "missing_from_selection":[{"article_id":i,"event_id":a[i]["event_id"],
                                    "source_url":a[i].get("source_url")} for i in absent],
        "changed_versions":[{"article_id":i,"before_version":a[i]["version"],
                             "after_version":b[i]["version"],
                             "before_event_id":a[i]["event_id"],
                             "after_event_id":b[i]["event_id"]} for i in changed],
        "interpretation":"Selection differences are not evidence of retraction or scientific replication.",
        "read_only":True,
    }


def main(argv=None):
    parser=argparse.ArgumentParser(description="KLONE E8 public-memory research radar and time machine")
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--question",type=str)
    group.add_argument("--compare-old",type=Path)
    parser.add_argument("--compare-new",type=Path)
    parser.add_argument("--klone-db",type=Path)
    parser.add_argument("--limit",type=int,default=48)
    parser.add_argument("--output",required=True,type=Path)
    args=parser.parse_args(argv)
    if args.question:
        if not args.klone_db:parser.error("--klone-db is required for radar")
        output=radar(args.klone_db,args.question,limit=args.limit)
    else:
        if not args.compare_new:parser.error("--compare-new required for time machine")
        a=json_object(read_bounded(args.compare_old,MAX_SNAPSHOT_BYTES))
        b=json_object(read_bounded(args.compare_new,MAX_SNAPSHOT_BYTES))
        output=compare_snapshots(a,b)
    write_new_report(args.output.expanduser(),
                     json.dumps(output,ensure_ascii=False,indent=2,allow_nan=False)+"\n",
                     Path.cwd().resolve())
    print(json.dumps({k:v for k,v in output.items() if k in
                      ("kind","query","matched","selected","snapshot_sha256")},
                      ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
