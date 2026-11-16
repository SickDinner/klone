"""KLONE E10: 72-seat Council research workbench, never a binding council vote.

Each seat receives one deterministic *pending* falsification/method-review task
for a current, real, PUBLIC research publication pair. No model inference,
network fetch, private memory, memory write, simulated vote, or autonomous
execution. The eight founder seats supervise their own eight lower rings.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from .council72 import catalog
from .evidence_io import write_new_report
from .limbo_source_dossiers import review_all

RING_FOCUS={
  1:("Tarkista julkaisun kanava ja alkuperä",
     "Erota ensisijainen tutkimus ja uutinen",
     "Tarkista URL ja muistiversio",
     "Selvitä julkaisuajan täsmällisyys",
     "Tunnista kirjoittajien tutkimuskenttä",
     "Etsi mahdollinen toissijainen tiivistelmä",
     "Tarkista lisenssi ennen jakelua",
     "Merkitse puuttuva alkuperäteksti"),
  2:("Muotoile ymmärrettävä kysymys",
     "Määritä väitteen rajat",
     "Kirjaa neutraali nollahypoteesi",
     "Erota hyöty ja tutkimustotuus",
     "Etsi käsitteen vaihtoehtoinen merkitys",
     "Kuvaa kohderyhmä ilman yleistystä",
     "Laadi julkinen epävarmuuskuvaus",
     "Määritä käyttäjän hyväksynnän rajat"),
  3:("Tarkista lähdeversioiden erot",
     "Erota tapahtuma ja julkaisun identiteetti",
     "Tarkista tapahtumien kronologia",
     "Merkitse muistin muuttumattomat tarkisteet",
     "Tunnista aineiston alkuperäinen keruuaika",
     "Hae puuttuvat korjaukset ja erratat",
     "Selvitä saman aineiston uudelleenkäyttö",
     "Määritä palautettava toistokoosteen rakenne"),
  4:("Arvioi tarvittava työmäärä",
     "Rajaa pienin falsifioiva koe",
     "Määritä kustannusten yläraja",
     "Erota laskenta ja laboratoriotyö",
     "Ehdota avoimen aineiston tarkistusta",
     "Priorisoi kriittiset epävarmuudet",
     "Määritä riippumaton vertailujärjestys",
     "Suunnittele rajattu omistajan hyväksyntä"),
  5:("Erota vahva väite ja heikko vihje",
     "Tunnista vahvistusharhan riski",
     "Tarkista valikoivan raportoinnin riski",
     "Merkitse kliinisen tulkinnan rajat",
     "Tarkista henkilö- ja terveystiedon suoja",
     "Kirjaa haitallisen käyttötulkinnan riski",
     "Erota narratiivi mittauksesta",
     "Suunnittele peruutettava seuraava askel"),
  6:("Tarkista tutkimusasetelma",
     "Määritä käytetty otos ja populaatio",
     "Tarkista mittausmenetelmät",
     "Tarkista tilastollinen malli",
     "Etsi sekoittavat tekijät",
     "Etsi mahdolliset vastakkaiset tulokset",
     "Arvioi aineiston riippumaton toistettavuus",
     "Rajaa käsitteellisen menetelmän siirrettävyys"),
  7:("Tarkista ympäristöjen eristys",
     "Tarkista päämuistin vain luku -raja",
     "Arvioi lähdeosoitteen käsittelyn turvallisuus",
     "Määritä toistettava analyysikomento",
     "Erota analyysin syöte ja tuloste",
     "Tarkista testien negatiiviset tapaukset",
     "Määritä versionhallittu raportti",
     "Suunnittele turvallinen palautus"),
  8:("Varmista alkuperäisen julkaisun tarkiste",
     "Erota lähteet ja samasta datasta tehdyt artikkelit",
     "Tarkista päätelmien todistustaakka",
     "Erota esijulkaisu ja vertaisarvioitu näyttö",
     "Tunnista uutisartikkelin evidenssiraja",
     "Tarkista auditoinnin jäljitettävyys",
     "Merkitse lähteiden riippumattomuuden puute",
     "Tarkista omistajan eksplisiittinen hyväksyntä"),
  9:("Valvo ulkorajan ja provenance-tietojen eheys",
     "Valvo tutkimuksen tavoitteen ja merkityksen rajoja",
     "Valvo muistin ja korjaushistorian jatkuvuutta",
     "Valvo resurssien ja kokeiden toteutettavuutta",
     "Valvo kuormitus-, haitta- ja ennakkoluuloriskejä",
     "Valvo ristiriitaisia teorioita ja falsifiointia",
     "Valvo arkkitehtuurin ja eristysrajojen säilymistä",
     "Valvo evidenssin, auditoinnin ja hyväksynnän ehtoja"),
}
RING_LABELS={
    1:"Lähteet ja ulkoraja",2:"Merkitys ja tutkimuskysymys",
    3:"Muistin jatkuvuus",4:"Resurssit ja mittaaminen",
    5:"Riskit ja vinoumat",6:"Menetelmät ja vastanäyttö",
    7:"Turvallinen toteutus",8:"Evidenssi ja oikeudet",
    9:"Kahdeksan perustajan valvonta",
}
SCHEMA=1


def _fingerprint(obj):
    encoded=json.dumps(obj,sort_keys=True,ensure_ascii=False,
                       separators=(",",":"),allow_nan=False)
    return sha256(encoded.encode("utf-8")).hexdigest()


def _assignment(member, dossier):
    ring=member["ring"]
    seat=member["slot"]
    if ring not in RING_FOCUS or not 1<=seat<=8:
        raise ValueError("invalid council ring or slot")
    return {
        "member_id":member["id"],"member_name":member["name"],
        "ring":ring,"slot":seat,
        "catalog_task":member["task"],
        "review_task":RING_FOCUS[ring][seat-1],
        "source_event_ids":[dossier["source_a"]["event_id"],
                            dossier["source_b"]["event_id"]],
        "founder":member["founder"],
        "oversees_ring":member["stewards_ring"] if member["founder"] else None,
        "status":"pending_human_or_agent_review",
        "completed":False,"evidence_checked":False,
        "vote_cast":False,"permission_granted":False,
    }


def _build(dossier):
    model=catalog()
    members=model["members"]
    if len(members)!=72 or len(model["rings"])!=9:
        raise ValueError("noncanonical Council72 catalog")
    expected=[(r,s) for r in range(1,10) for s in range(1,9)]
    actual=sorted((m["ring"],m["slot"]) for m in members)
    if actual!=expected:
        raise ValueError("Council72 has missing or duplicated seats")
    seat_map={(m["ring"],m["slot"]):m for m in members}
    seats=[_assignment(seat_map[x],dossier) for x in expected]
    founders=[s for s in seats if s["founder"]]
    if len(founders)!=8 or sorted(s["oversees_ring"] for s in founders)!=list(range(1,9)):
        raise ValueError("Council72 founder ring not canonical")
    rings=[{"ring":r,"name":RING_LABELS[r],"assigned_seats":8,
            "pending_seats":8,
            "member_ids":[s["member_id"] for s in seats if s["ring"]==r],
            "active_vote_count":0,
            "founder_supervisor_id":(next(
                s["member_id"] for s in founders if s["oversees_ring"]==r)
                if r<9 else None)} for r in range(1,10)]
    a,b=dossier["source_a"],dossier["source_b"]
    risks=[]
    if dossier["source_comparison_type"]=="mixed_news_or_reference_pair":
        risks.append("news_is_not_independent_study")
    if dossier["independence"]["same_publisher_group"]:
        risks.append("same_publisher_group_not_independent_study")
    if any(s["source_class"]=="research_preprint" for s in (a,b)):
        risks.append("preprint_peer_review_not_confirmed")
    risks += ["full_text_not_reviewed","methods_not_compared",
              "shared_dataset_not_checked","replication_not_demonstrated"]
    summary={
        "source_a":{"event_id":a["event_id"],"title":a["title"],
                    "source_url":a["source_url"],"receipt_sha256":a["receipt_sha256"],
                    "source_class":a["source_class"],"version":a["version"]},
        "source_b":{"event_id":b["event_id"],"title":b["title"],
                    "source_url":b["source_url"],"receipt_sha256":b["receipt_sha256"],
                    "source_class":b["source_class"],"version":b["version"]},
        "shared_concepts":dossier["common_non_generic_terms"],
        "source_comparison_type":dossier["source_comparison_type"],
        "evidence_debt":sorted(set(risks)),
    }
    result={
        "kind":"klone-atlas-e10-council72-workbench",
        "schema_version":SCHEMA,
        "source_snapshot_sha256":_fingerprint(summary),
        "source_summary":summary,
        "catalog_model_version":model["model_version"],
        "catalog_sha256":_fingerprint(model),
        "rings":rings,"assigned_seats":seats,
        "seat_count":72,"ring_count":9,"founder_count":8,
        "pending_review_count":72,"performed_review_count":0,
        "research_evidence_debt":summary["evidence_debt"],
        "recommendation":"Do not approve or act; open primary studies and collect actual methods/results.",
        "decision_state":"awaiting_real_review_and_owner_approval",
        "authority":{"binding_vote":False,"memory_write":False,
                     "external_network_actions":False,"private_room_read":False,
                     "hypothesis_verified":False,"autonomous_experiment":False,
                     "owner_approval_obtained":False,
                     "consciousness_claim":False},
    }
    result["report_sha256"]=_fingerprint(result)
    return result


def council_review(core_db,first_event_id,second_event_id,*,question="genetiikka"):
    """Only canonical, currently active E9.1 source pairs qualify."""
    if type(first_event_id) is not int or type(second_event_id) is not int:
        raise ValueError("real public source event IDs required")
    dossiers=review_all(core_db,question=question)["dossiers"]
    for d in dossiers:
        ids={d["source_a"]["event_id"],d["source_b"]["event_id"]}
        if ids=={first_event_id,second_event_id} and len(ids)==2:
            return _build(d)
    raise ValueError("pair is not a current canonical E9.1 public source pair")


def council_all(core_db,*,question="genetiikka",max_pairs=8):
    if type(max_pairs) is not int or not 1<=max_pairs<=8:
        raise ValueError("max_pairs must be 1..8")
    batch=review_all(core_db,question=question)
    all_rows=[_build(x) for x in batch["dossiers"][:max_pairs]]
    return {"kind":"klone-atlas-e10-council72-batch","schema_version":SCHEMA,
            "source_question":question,
            "unique_source_pairs_available":batch["candidate_count"],
            "board_count":len(all_rows),"boards":all_rows,
            "total_pending_seat_assignments":len(all_rows)*72,
            "authority":{"memory_write":False,"external_network_actions":False,
                         "auto_votes":False,"scientific_truth_verified":False}}


def main(argv=None):
    parser=argparse.ArgumentParser(description="KLONE E10, 72-seat read-only research board")
    parser.add_argument("--klone-db",type=Path,required=True)
    parser.add_argument("--question",default="genetiikka")
    choice=parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--pair",nargs=2,type=int,metavar=("FIRST","SECOND"))
    choice.add_argument("--all",action="store_true")
    parser.add_argument("--max-pairs",type=int,default=8)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args(argv)
    try:
        out=(council_all(args.klone_db,question=args.question,
                         max_pairs=args.max_pairs)
             if args.all else
             council_review(args.klone_db,*args.pair,question=args.question))
        write_new_report(args.output.expanduser(),
                         json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+"\n",
                         Path.cwd().resolve())
    except (ValueError,PermissionError,OSError) as exc:
        parser.error(str(exc))
    print(json.dumps({"kind":out["kind"],
                      "boards":out.get("board_count",1),
                      "pending_assignments":out.get("total_pending_seat_assignments",72),
                      "memory_write":False},ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
