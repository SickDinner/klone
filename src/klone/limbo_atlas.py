"""KLONE Limbo Atlas E2: multidisciplinary public-source research with Council 72 routing.

All external reads require an explicit CLI --fetch; APIs never fetch or post.
Headlines and abstracts are unverified claims, not automatically authenticated evidence.
No external identity impersonation, autonomous publishing or private-room access.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import ssl
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, ProxyHandler, Request, build_opener
import xml.etree.ElementTree as ET

from .council72 import catalog
from .council72_session import run_session
from .evidence_io import write_new_report
from .limbo_external import MAX_BYTES, _feed_text

ATOM = "{http://www.w3.org/2005/Atom}"
MAX_RESULTS = 6
MAX_RECORDS = 48
MAX_SOURCES_PER_RUN = 32
ARXIV_API = "https://export.arxiv.org/api/query"
PMC_API = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
USER_AGENT = "KLONE-LimboAtlas/0.2 (public source research, no publishing)"

@dataclass(frozen=True)
class Domain:
    id: str
    courier: int
    title: str
    scope: str
    preferred_ring: int
    research_question: str

# Actual courier IDs/roles from Council 72. No independent bot identities.
DOMAINS = (
    Domain("geopolitics", 24, "Geopolitiikka, turvallisuus ja kansainväliset suhteet",
           "Valtiot, diplomatia, kansainvälinen oikeus, konfliktien vaikutukset, muuttoliike", 8,
           "Miten väitteen lähteet, intressit ja vaihtoehtoiset tulkinnat voidaan tarkistaa?"),
    Domain("economics", 27, "Talous, työmarkkinat ja rahoitus",
           "Makrotalous, yritykset, eriarvoisuus, työllisyys, julkinen talous", 4,
           "Mitä taloudellisia seurauksia, jakaumia ja epävarmuuksia väitteeseen sisältyy?"),
    Domain("technology", 30, "Tekoäly, tietotekniikka ja insinööritieteet",
           "Agentit, muistijärjestelmät, robotiikka, tietoturva, laskenta", 7,
           "Mikä on teknisesti toistettavissa, falsifioitavissa ja toteutettavissa?"),
    Domain("society", 53, "Yhteiskunta, koulutus ja kansanterveys",
           "Sosiologia, koulutus, terveysjärjestelmät, viestintä, antropologia", 5,
           "Miten yhteisövaikutukset ja tutkimusasetelman rajat erotetaan tulkinnoista?"),
    Domain("genetics", 55, "Genetiikka, genomit ja evoluutio",
           "Populaatiogenetiikka, muinais-DNA, periytyvyys, genomiikka, bioinformatiikka", 3,
           "Miten aineiston laatu, sukulaisuusmallit ja vaihtoehtoiset selitykset arvioidaan?"),
    Domain("natural_sciences", 70, "Ilmasto, energia, fysiikka ja avaruus",
           "Geofysiikka, ilmasto, tähtitiede, energiajärjestelmät, ympäristötiede", 6,
           "Mitkä havainnot, mallit ja riippumattomat mittaukset tukevat tulosta?"),
    Domain("mind_medicine", 11, "Psykiatria, psykologia, neurotiede ja farmakologia",
           "Kognitio, neuropsykiatria, psykologiset menetelmät, lääkekehitys, haittatutkimus", 5,
           "Miten kliininen näyttö, mekanismi, haitat ja kausaalitulkinta erotetaan?"),
    Domain("philosophy", 71, "Filosofia, historia, uskonnot ja taide",
           "Etiikka, tietoteoria, kulttuurihistoria, uskontotiede, kuvataide", 2,
           "Mitä käsitteellisiä oletuksia, historiallisia eroja ja vasta-argumentteja väite sisältää?"),
)
BY_DOMAIN = {d.id: d for d in DOMAINS}
BY_COURIER = {d.courier: d for d in DOMAINS}
assert len(BY_DOMAIN) == len(BY_COURIER) == 8


@dataclass(frozen=True)
class AtlasSource:
    id: str
    domain: str
    kind: str  # rss, arxiv, europepmc
    publisher: str
    query: str  # fixed category, term expression, or full https feed URL
    allowed_hosts: tuple[str, ...]
    description: str

# Fixed publication-focused registry. Unsupported links are rejected, not followed.
SOURCES = (
    AtlasSource("bbc-world", "geopolitics", "rss", "bbc", "https://feeds.bbci.co.uk/news/world/rss.xml",
                ("bbc.com", "www.bbc.com", "bbc.co.uk", "www.bbc.co.uk"), "Kansainväliset uutiset"),
    AtlasSource("guardian-world", "geopolitics", "rss", "guardian", "https://www.theguardian.com/world/rss",
                ("www.theguardian.com", "theguardian.com"), "Toinen erillinen uutistoimitus"),
    AtlasSource("bbc-business", "economics", "rss", "bbc", "https://feeds.bbci.co.uk/news/business/rss.xml",
                ("bbc.com", "www.bbc.com", "bbc.co.uk", "www.bbc.co.uk"), "Talouden uutiset"),
    AtlasSource("arxiv-econ", "economics", "arxiv", "arxiv", "econ.GN",
                ("arxiv.org", "www.arxiv.org"), "Yleinen taloustiede / esijulkaisut"),
    AtlasSource("arxiv-finance", "economics", "arxiv", "arxiv", "q-fin.EC",
                ("arxiv.org", "www.arxiv.org"), "Rahoitus ja talousmallit"),
    AtlasSource("bbc-technology", "technology", "rss", "bbc", "https://feeds.bbci.co.uk/news/technology/rss.xml",
                ("bbc.com", "www.bbc.com", "bbc.co.uk", "www.bbc.co.uk"), "Teknologiauutiset"),
    AtlasSource("atlas-arxiv-ai", "technology", "arxiv", "arxiv", "cs.AI",
                ("arxiv.org", "www.arxiv.org"), "Tekoäly ja agentit"),
    AtlasSource("arxiv-ml", "technology", "arxiv", "arxiv", "cs.LG",
                ("arxiv.org", "www.arxiv.org"), "Koneoppiminen"),
    AtlasSource("bbc-health", "society", "rss", "bbc", "https://feeds.bbci.co.uk/news/health/rss.xml",
                ("bbc.com", "www.bbc.com", "bbc.co.uk", "www.bbc.co.uk"), "Terveysjärjestelmät"),
    AtlasSource("bbc-education", "society", "rss", "bbc", "https://feeds.bbci.co.uk/news/education/rss.xml",
                ("bbc.com", "www.bbc.com", "bbc.co.uk", "www.bbc.co.uk"), "Koulutus ja yhteisöt"),
    AtlasSource("smithsonian-innovation", "society", "rss", "smithsonian", "https://www.smithsonianmag.com/rss/innovation/",
                ("smithsonianmag.com", "www.smithsonianmag.com"), "Kulttuurin ja innovaatioiden uutiset"),
    AtlasSource("genomics-arxiv", "genetics", "arxiv", "arxiv", "q-bio.GN",
                ("arxiv.org", "www.arxiv.org"), "Laskennallinen genomiikka"),
    AtlasSource("population-arxiv", "genetics", "arxiv", "arxiv", "q-bio.PE",
                ("arxiv.org", "www.arxiv.org"), "Populaatiot ja evoluutio"),
    AtlasSource("genomics-pmc", "genetics", "europepmc", "europepmc",
                "genomics AND (population OR evolution)", ("europepmc.org", "www.europepmc.org"),
                "Julkaisut genomiikasta ja evoluutiosta"),
    AtlasSource("ancient-dna-pmc", "genetics", "europepmc", "europepmc",
                '"ancient DNA" OR paleogenomics', ("europepmc.org", "www.europepmc.org"),
                "Muinais-DNA ja paleogenomiikka"),
    AtlasSource("bbc-science", "natural_sciences", "rss", "bbc",
                "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
                ("bbc.com", "www.bbc.com", "bbc.co.uk", "www.bbc.co.uk"), "Ympäristö- ja tiedeuutiset"),
    AtlasSource("nasa-news", "natural_sciences", "rss", "nasa", "https://www.nasa.gov/feed/",
                ("nasa.gov", "www.nasa.gov", "science.nasa.gov"), "Avaruustutkimuksen julkaisut"),
    AtlasSource("earth-arxiv", "natural_sciences", "arxiv", "arxiv", "physics.geo-ph",
                ("arxiv.org", "www.arxiv.org"), "Geofysiikka"),
    AtlasSource("quantum-arxiv", "natural_sciences", "arxiv", "arxiv", "quant-ph",
                ("arxiv.org", "www.arxiv.org"), "Kvanttifysiikka"),
    AtlasSource("psychiatry-pmc", "mind_medicine", "europepmc", "europepmc",
                "psychiatry AND (trial OR review)", ("europepmc.org", "www.europepmc.org"),
                "Psykiatrian kliininen näyttö"),
    AtlasSource("psychology-pmc", "mind_medicine", "europepmc", "europepmc",
                "psychology AND (experiment OR systematic review)", ("europepmc.org", "www.europepmc.org"),
                "Psykologian tutkimusmenetelmät"),
    AtlasSource("pharmacology-pmc", "mind_medicine", "europepmc", "europepmc",
                "pharmacology AND (safety OR adverse effects)", ("europepmc.org", "www.europepmc.org"),
                "Farmakologia ja lääketurvallisuus"),
    AtlasSource("neuro-arxiv", "mind_medicine", "arxiv", "arxiv", "q-bio.NC",
                ("arxiv.org", "www.arxiv.org"), "Neuroverkostot ja kognitio"),
    AtlasSource("stanford-philosophy", "philosophy", "rss", "stanford",
                "https://plato.stanford.edu/rss/sep.xml", ("plato.stanford.edu",),
                "Stanford Encyclopedia of Philosophy: uudet ja päivitetyt artikkelit"),
    AtlasSource("smithsonian-arts", "philosophy", "rss", "smithsonian",
                "https://www.smithsonianmag.com/rss/arts-culture/",
                ("smithsonianmag.com", "www.smithsonianmag.com"), "Kulttuuri ja taide"),
    AtlasSource("history-philosophy-arxiv", "philosophy", "arxiv", "arxiv", "physics.hist-ph",
                ("arxiv.org", "www.arxiv.org"), "Fysiikan historia ja filosofia"),
)
BY_SOURCE = {s.id: s for s in SOURCES}
assert len(BY_SOURCE) == len(SOURCES) and len(SOURCES) == 26


def _digest(value) -> str:
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                             separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _text(value, cap=360, *, truncate=False) -> str:
    if not isinstance(value, str):
        raise ValueError("text must be string")
    if not truncate and len(value) > cap:
        raise ValueError("text exceeds field limit")
    cleaned = _feed_text(value, cap)
    if not cleaned or any(ord(c) < 32 for c in cleaned):
        raise ValueError("invalid text")
    return cleaned


def _article_url(url: str, source: AtlasSource, *, imported_arxiv_link=False) -> str:
    if not isinstance(url, str) or not 12 <= len(url) <= 256:
        raise ValueError("article URL invalid or too long")
    try:
        p = urlsplit(url)
        host, port = p.hostname, p.port
    except ValueError as exc:
        raise ValueError("article URL invalid") from exc
    if not host or host.lower().rstrip(".") not in source.allowed_hosts or p.fragment or (
            p.username is not None or p.password is not None) or (
            any(ord(c) < 33 for c in url)):
        raise ValueError("article host not approved")
    if (imported_arxiv_link and source.kind == "arxiv" and p.scheme == "http"
            and port in (None, 80) and p.path.startswith("/abs/")):
        url = "https://arxiv.org" + p.path + ("?" + p.query if p.query else "")
        p = urlsplit(url)
        port = p.port
    if p.scheme != "https" or port not in (None, 443):
        raise ValueError("article must use HTTPS")
    return url


def _rss_docs(raw: bytes, source: AtlasSource) -> list[dict]:
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_BYTES:
        raise ValueError("oversized or empty XML response")
    upper = raw.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise ValueError("DTD/entities rejected")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValueError("invalid XML") from exc
    if root.tag == "rss":
        items, atom = root.findall("./channel/item"), False
    elif root.tag == ATOM+"feed":
        items, atom = root.findall(ATOM+"entry"), True
    elif root.tag.endswith("}RDF"):
        items, atom = [el for el in root if el.tag.endswith("}item")], False
    else:
        raise ValueError("not RSS or Atom")
    out, seen = [], set()
    for item in items[:MAX_RESULTS * 5]:
        if atom:
            get = lambda k: item.findtext(ATOM+k, default="")
            links = [e.attrib.get("href", "") for e in item.findall(ATOM+"link")
                     if e.attrib.get("rel", "alternate") == "alternate"]
            url, title, body, published = (links[0] if links else get("id")), get("title"), \
                (get("summary") or get("content") or get("title")), (get("published") or get("updated"))
        else:
            get = lambda k: item.findtext(k, default="")
            url, title, body, published = get("link"), get("title"), (get("description") or get("title")), get("pubDate")
        try:
            article = _article_url(url, source, imported_arxiv_link=True)
            doc = {"source_id":source.id, "courier_id":BY_DOMAIN[source.domain].courier,
                   "url":article, "title":_text(title,240,truncate=True),
                   "summary":_text(body,360,truncate=True),
                   "published_at":_text(published,80,truncate=True) if published else None}
        except ValueError:
            continue
        if article not in seen:
            seen.add(article); out.append(doc)
        if len(out) >= MAX_RESULTS:
            break
    return out


def _pmc_docs(raw: bytes, source: AtlasSource) -> list[dict]:
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_BYTES:
        raise ValueError("invalid Europe PMC JSON size")
    try:
        data = json.loads(raw)
        rows = data["resultList"]["result"]
    except (ValueError, TypeError, KeyError) as exc:
        raise ValueError("invalid Europe PMC response") from exc
    if not isinstance(rows, list):
        raise ValueError("invalid Europe PMC result list")
    out, seen = [], set()
    for row in rows[:MAX_RESULTS*4]:
        if not isinstance(row, dict):
            continue
        kind, ident = row.get("source"), row.get("id")
        if (kind not in ("MED", "PMC", "PPR")
                or not isinstance(ident,str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,40}",ident)):
            continue
        url = "https://europepmc.org/article/" + kind + "/" + ident
        try:
            doc={"source_id":source.id,"courier_id":BY_DOMAIN[source.domain].courier,
                 "url":_article_url(url, source),
                 "title":_text(row.get("title", ""),240,truncate=True),
                 "summary":_text(row.get("abstractText") or row.get("title") or "",360,truncate=True),
                 "published_at":_text(row["firstPublicationDate"],80,truncate=True)
                   if row.get("firstPublicationDate") else None}
        except ValueError:
            continue
        if url not in seen: seen.add(url);out.append(doc)
        if len(out)>=MAX_RESULTS:break
    return out


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _query_url(source: AtlasSource) -> str:
    if source.kind == "arxiv":
        return ARXIV_API + "?" + urlencode({
            "search_query":"cat:"+source.query, "start":0,"max_results":MAX_RESULTS,
            "sortBy":"submittedDate","sortOrder":"descending",
        })
    if source.kind == "europepmc":
        return PMC_API + "?" + urlencode({
            "query":source.query+" sort_date:y","format":"json",
            "resultType":"core","pageSize":MAX_RESULTS,
        })
    return source.query


def fetch_source(source_id: str, *, timeout: float = 12.0) -> list[dict]:
    if source_id not in BY_SOURCE:
        raise ValueError("source not in fixed atlas registry")
    if type(timeout) not in (float,int) or not 1<=timeout<=15:
        raise ValueError("invalid timeout")
    source=BY_SOURCE[source_id]
    endpoint=_query_url(source)
    opener=build_opener(ProxyHandler({}), HTTPSHandler(context=ssl.create_default_context()), _NoRedirect())
    request=Request(endpoint,headers={"User-Agent":USER_AGENT,
                       "Accept":"application/json" if source.kind=="europepmc"
                       else "application/xml, application/atom+xml, application/rss+xml, text/xml"})
    try:
        with opener.open(request,timeout=timeout) as response:
            if response.status!=200 or response.url!=endpoint:
                raise ValueError("source status/endpoint mismatch")
            kind=response.headers.get("Content-Type","").lower()
            if kind and (("json" not in kind) if source.kind=="europepmc" else ("xml" not in kind and "text/plain" not in kind)):
                raise ValueError("unexpected content type")
            raw=response.read(MAX_BYTES+1)
    except (HTTPError,URLError,TimeoutError,OSError) as exc:
        raise ValueError("source fetch failed ("+source_id+"): "+str(exc)[:120]) from exc
    return _pmc_docs(raw,source) if source.kind=="europepmc" else _rss_docs(raw,source)


def roster() -> dict:
    model=catalog()
    couriers={m["id"]:m for m in model["members"] if m["ring"]==1}
    if set(couriers)!=set(BY_COURIER):
        raise ValueError("Council72 Limbo roster changed")
    domain_rows=[]
    for d in DOMAINS:
        member=couriers[d.courier]
        ring=model["rings"][d.preferred_ring-1]
        domain_rows.append({
            "id":d.id,"name":d.title,"scope":d.scope,"courier_id":d.courier,
            "agent_name":member["name"],"slot":member["slot"],
            "founder_id":member["courier_for"],"existing_task":member["task"],
            "neuromodulators":dict(member["baseline_modulators"]),
            "preferred_ring":ring["id"],"ring_name":ring["dante_label"],
            "research_question":d.research_question,
            "sources":[s.id for s in SOURCES if s.domain==d.id],
        })
    return {"schema_version":2,"domains":domain_rows,
            "sources":[{"id":s.id,"domain":s.domain,"kind":s.kind,
                        "publisher":s.publisher,"description":s.description,
                        "source_url":_query_url(s)}
                       for s in SOURCES],
            "authority":{"external_posting":False,"network_via_api":False,
                         "private_memory_access":False,"human_review_required":True}}


def validate_records(records) -> list[dict]:
    if not isinstance(records,list) or not 1<=len(records)<=MAX_RECORDS:
        raise ValueError("one to 48 observations required")
    seen=set();out=[]
    for raw in records:
        if not isinstance(raw,dict) or set(raw)-{"source_id","courier_id","url","title","summary","published_at"}:
            raise ValueError("unexpected observation fields")
        sid=raw.get("source_id")
        if type(sid) is not str or sid not in BY_SOURCE:
            raise ValueError("unapproved source")
        spec=BY_SOURCE[sid]
        expected=BY_DOMAIN[spec.domain].courier
        if type(raw.get("courier_id")) is not int or raw["courier_id"]!=expected:
            raise ValueError("wrong courier for source")
        url=_article_url(raw.get("url"),spec)
        title=_text(raw.get("title"),240)
        summary=_text(raw.get("summary"),360)
        published=raw.get("published_at")
        if published is not None:published=_text(published,80)
        key=(sid,url)
        if key in seen:raise ValueError("duplicate publication")
        seen.add(key)
        out.append({"source_id":sid,"courier_id":expected,"url":url,
                    "title":title,"summary":summary,"published_at":published,
                    "publisher_group":spec.publisher,"domain":spec.domain,
                    "source_type":spec.kind,
                    "receipt_sha256":_digest((sid,url,title,summary,published)),
                    "epistemic_status":"unverified_publisher_claim"})
    return out


IDEA_METHODS = (
    "Muodosta täsmällinen käsitemääritelmä ja erottele lähteen väite havainnosta.",
    "Etsi aineiston ulkopuolinen vertailututkimus ja arvioi sen riippumattomuus.",
    "Tarkista poikkeukset, aineiston vinoumat, puuttuvat mittarit ja haittamahdollisuudet.",
    "Luo vaihtoehtoinen hypoteesi, joka selittää saman havainnon eri mekanismilla.",
    "Suunnittele testi, jonka tulos voisi osoittaa ehdotetun selityksen vääräksi.",
    "Ehdota kahden tieteenalan välistä uutta tutkimuskysymystä, merkiten sen hypoteesiksi.",
    "Listaa toistettavan kokeen aineisto, menetelmät ja epävarmuusrajat.",
    "Laadi varovainen johtopäätös ja tärkein avoimeksi jäänyt kysymys.",
)


def _ring_ideation(model: dict, ring_id: int, headline: str) -> list[dict]:
    """Eight existing specialists per target ring propose separate research angles.

    These are deterministic, source-grounded *draft prompts*, not generated
    evidence, independent minds, autonomous task execution or peer review.
    """
    members = sorted((m for m in model["members"] if m["ring"] == ring_id),
                     key=lambda member: member["slot"])
    if len(members) != 8:
        raise ValueError("Council72 specialist ring must contain eight members")
    ideas = []
    for member, method in zip(members, IDEA_METHODS):
        ideas.append({
            "member_id": member["id"],
            "name": member["name"],
            "specialism": member["task"],
            "slot": member["slot"],
            "strategy": method,
            "research_prompt": ("Aihe: " + headline[:160] + ". Erikoisala: " +
                                member["task"] + ". " + method),
            "kind": "deterministic_ideation_draft",
            "evidence_authenticated": False,
            "execution_enabled": False,
        })
    return ideas


def _packet(records: list[dict],ring_id: int, question: str | None) -> dict:
    model=catalog()
    if type(ring_id) is not int or not 2<=ring_id<=8:
        raise ValueError("specialist target ring must be 2..8")
    ring=model["rings"][ring_id-1]
    selected=records[:8]
    if not selected:raise ValueError("packet requires at least one observation")
    user_question=_text(question,380) if question is not None else "Mitä voimme osoittaa ja mitä emme vielä tiedä?"
    groups=sorted({r["publisher_group"] for r in selected})
    identities=[r["receipt_sha256"][:20] for r in selected]
    question_examples=[]
    for r in selected[:4]:
        question_examples.append("Tarkista lähteen '"+r["title"]+"' aineisto ja vaihtoehtoinen tulkinta.")
    return {
        "packet_id":"atlas:"+_digest([ring_id,identities,user_question])[:24],
        "status":"draft_requires_specialist_review",
        "target_ring":ring_id,"target_ring_name":ring["dante_label"],
        "specialist_domain":ring["domain"],
        "steward_id":ring["steward_id"],"source_couriers":sorted({r["courier_id"] for r in selected}),
        "headline":selected[0]["title"],
        "question":user_question,
        "questions":question_examples,
        "specialist_ideas":_ring_ideation(model,ring_id,selected[0]["title"]),
        "proposed_work":["Etsi alkuperäinen julkaisu ja koko aineisto.",
                         "Arvioi metodologia, epävarmuus ja mahdolliset vastaesimerkit.",
                         "Hae riippumaton julkaisija ja tarkista tulkinnan rajat.",
                         "Laadi kaksi kilpailevaa selitystä ja falsifioitava tarkistus.",
                         "Raportoi johtopäätökset perustajalle vain lähdeviittein."],
        "reference_urls":[r["url"] for r in selected],
        "receipt_ids":identities,"publisher_groups":groups,
        "independent_sources_verified":False,
        "truth_verified":False,"human_review_required":True,
        "network_action":False,"publication_enabled":False,
        "classification":"public",
    }


def plan(records: object, *, ring_id: int | None = None,
         question: str | None = None) -> dict:
    """Cross-discipline routing without changing Council72 catalog or permissions."""
    data=validate_records(records)
    if ring_id is not None and (type(ring_id) is not int or not 2<=ring_id<=8):
        raise ValueError("ring_id must be an integer 2..8")
    if question is not None:_text(question,380)
    packets=[]
    if ring_id is not None:
        for i in range(0,len(data),8):
            packets.append(_packet(data[i:i+8],ring_id,question))
    else:
        for target in range(2,9):
            own=[r for r in data if BY_DOMAIN[r["domain"]].preferred_ring==target]
            for i in range(0,len(own),8):
                packets.append(_packet(own[i:i+8],target,question))
    observations=[]
    for r in data:
        observations.append({
            "id":"atlas:"+r["receipt_sha256"][:20],
            "courier_id":r["courier_id"],"source_ref":r["url"],
            "source_group":r["publisher_group"],
            "claim_key":"lead:"+r["receipt_sha256"][:22],
            "stance":"unknown","summary":(r["title"]+": "+r["summary"])[:512],
            "classification":"public","observed_at":r["published_at"],
            "signals":{"evidence_quality":.15,"uncertainty":1.0,"risk":.25,
                       "novelty":.25,"reward":0.0,"threat":0.0,"social_feedback":0.0},
        })
    # The existing Council72 session receives the original courier identities.
    # All data is unknown; a feed is not proof of a research claim.
    request={"session_id":"atlas."+_digest(data)[:16],
             "goal":"Julkisen datan monialainen tutkiminen ja reititetty luonnostelu",
             "classification":"public","source_kind":"user_claims",
             "steps":[{"observations":observations[i:i+32]}
                      for i in range(0,len(observations),32)]}
    council=run_session(request)
    # Preserve six existing simulated neuromodulators for each member's
    # *proposal*, without turning the simulated vote into any authority.
    opinions={o["member_id"]:o for o in council["latest_experiment"]["modulated"]["opinions"]}
    for packet in packets:
        for idea in packet["specialist_ideas"]:
            opinion=opinions[idea["member_id"]]
            idea["simulated_modulators"]=dict(opinion["modulators"])
            idea["simulated_affect"]=dict(opinion["affect"])
            idea["vote_preview"]=opinion["vote"]
    return {"schema_version":2,"kind":"klone-limbo-atlas-preview",
            "observations":data,"source_groups":sorted({r["publisher_group"] for r in data}),
            "packets":packets,"council_session":council,
            "input_sha256":_digest(data),
            "authority":{"external_posting":False,"private_memory_access":False,
                         "automatic_approval":False,"human_review_required":True},
            "epistemic_status":"unverified_publisher_reports"}


def balanced_selection(observations: list[dict], *, limit: int = MAX_RECORDS) -> list[dict]:
    """Round-robin sources *within* each domain, then round-robin the domains.

    A large --all batch must not hide psychology, philosophy or genetics merely
    because geopolitics news was fetched first. Preserve fixed source provenance.
    """
    if type(limit) is not int or not 1 <= limit <= MAX_RECORDS:
        raise ValueError("invalid output limit")
    pools = {d.id: {} for d in DOMAINS}
    for record in observations:
        source = BY_SOURCE.get(record.get("source_id"))
        if source is None:
            raise ValueError("unknown source in balanced selection")
        pools[source.domain].setdefault(source.id, []).append(record)
    ordered = {}
    for domain in DOMAINS:
        group = pools[domain.id]
        arranged = []
        while any(group.values()):
            for sid in sorted(group):
                if group[sid]:
                    arranged.append(group[sid].pop(0))
        ordered[domain.id] = arranged
    selected = []
    while len(selected) < limit and any(ordered.values()):
        for domain in DOMAINS:
            if ordered[domain.id] and len(selected) < limit:
                selected.append(ordered[domain.id].pop(0))
    return selected


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description="Manually fetch curated multidisciplinary sources; no posting.")
    parser.add_argument("--fetch",action="store_true")
    parser.add_argument("--domain",choices=sorted(BY_DOMAIN),action="append")
    parser.add_argument("--source",choices=sorted(BY_SOURCE),action="append")
    parser.add_argument("--all",action="store_true",help="Opt in to all curated sources")
    parser.add_argument("--output",required=True,help="Fresh JSON report path; existing files are not replaced")
    parser.add_argument("--memory-db",type=Path,help="Opt in to archiving ALL retrieved public entries in standalone E3 SQLite database")
    parser.add_argument("--memory-delta-output",type=Path,help="Optional new E3 delta report; requires --memory-db")
    args=parser.parse_args(argv)
    if not args.fetch:parser.error("--fetch is required")
    if args.memory_delta_output and not args.memory_db:parser.error("--memory-delta-output needs --memory-db")
    if args.all and (args.domain or args.source):parser.error("--all cannot combine with filters")
    if not (args.all or args.domain or args.source):parser.error("select --domain, --source or --all")
    if args.all: selected=list(BY_SOURCE)
    elif args.source: selected=list(dict.fromkeys(args.source))
    else: selected=[s.id for s in SOURCES if s.domain in set(args.domain)]
    if len(selected)>MAX_SOURCES_PER_RUN:raise SystemExit("source count limit exceeded")
    observations=[];errors=[]; last_arxiv=None
    for sid in selected:
        source=BY_SOURCE[sid]
        if source.kind=="arxiv":
            # arXiv API requests are paced across categories.
            if last_arxiv is not None:
                elapsed=time.monotonic()-last_arxiv
                if elapsed<3.1:time.sleep(3.1-elapsed)
            last_arxiv=time.monotonic()
        try:
            results=fetch_source(sid)
            observations.extend(results)
            if not results:errors.append({"source_id":sid,"status":"empty"})
        except ValueError as exc:
            errors.append({"source_id":sid,"status":"error","detail":str(exc)})
    if not observations:
        raise SystemExit("No source observations. "+json.dumps(errors,ensure_ascii=False))
    archive_delta=None
    if args.memory_db is not None:
        # Explicit user opt-in. Store ALL retrieved entries, including those
        # omitted from the bounded 48-observation Council72 planning sample.
        from .limbo_memory import ingest as memory_ingest
        archive_delta=memory_ingest(args.memory_db, observations)
        if args.memory_delta_output:
            rendered=json.dumps(archive_delta,ensure_ascii=False,indent=2,allow_nan=False)+"\n"
            write_new_report(args.memory_delta_output.expanduser(),rendered,Path.cwd().resolve())
    report=plan(balanced_selection(observations))
    report.update({"collection":"manual_public_web",
                   "collected_at_utc":datetime.now(timezone.utc).isoformat(),
                   "requested_sources":selected,"fetch_errors":errors,
                   "dropped_after_cap":max(0,len(observations)-MAX_RECORDS)})
    text=json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n"
    write_new_report(Path(args.output).expanduser(),text,Path.cwd().resolve())
    print(json.dumps({"path":args.output,"memory":archive_delta["counts"] if archive_delta else None,"observations":len(report["observations"]),
                      "packets":len(report["packets"]),"errors":len(errors),
                      "dropped_after_cap":report["dropped_after_cap"]},ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
