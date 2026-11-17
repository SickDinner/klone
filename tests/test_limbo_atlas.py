"""Regression tests for Limbo Atlas E2 multidisciplinary source and ring routing."""
import json
from urllib.parse import urlencode
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from klone.council72 import catalog
from klone.limbo_atlas import (
    BY_DOMAIN, BY_SOURCE, DOMAINS, SOURCES, _rss_docs, _pmc_docs,
    _query_url, balanced_selection, fetch_source, main, plan, roster,
    validate_records,
)
from klone.main import create_app


def paper(source_id, serial="1"):
    s=BY_SOURCE[source_id]
    if s.kind=="arxiv":
        url="https://arxiv.org/abs/2611.1000"+serial
    elif s.kind=="europepmc":
        url="https://europepmc.org/article/MED/12345"+serial
    elif s.publisher=="stanford":
        url="https://plato.stanford.edu/entries/moral-psychology-"+serial+"/"
    elif s.publisher=="guardian":
        url="https://www.theguardian.com/world/2026/nov/15/test-"+serial
    elif s.publisher=="smithsonian":
        url="https://www.smithsonianmag.com/science-nature/test-"+serial+"/"
    elif s.publisher=="nasa":
        url="https://www.nasa.gov/news-release/test-"+serial+"/"
    else:
        url="https://www.bbc.com/news/articles/test-"+serial
    return {"source_id":source_id,"courier_id":BY_DOMAIN[s.domain].courier,
            "url":url,"title":"Test publication "+serial,
            "summary":"Reported experimental result (test fixture).",
            "published_at":"2026-11-15"}


class AtlasE2Tests(unittest.TestCase):
    def setUp(self):
        self.client=TestClient(create_app())

    def test_eight_domains_have_real_couriers_and_modulators(self):
        model=catalog()
        actual={m["id"]:m for m in model["members"] if m["ring"]==1}
        result=roster()
        self.assertEqual(result["schema_version"],2)
        self.assertEqual(len(result["domains"]),8)
        self.assertEqual({x["courier_id"] for x in result["domains"]},set(actual))
        self.assertEqual(len(result["sources"]),26)
        self.assertEqual(len({s.id for s in SOURCES}),26)
        for d in result["domains"]:
            member=actual[d["courier_id"]]
            self.assertEqual(d["agent_name"],member["name"])
            self.assertEqual(d["founder_id"],member["courier_for"])
            self.assertEqual(d["neuromodulators"],member["baseline_modulators"])
            self.assertEqual(len(d["neuromodulators"]),6)
            self.assertGreaterEqual(len(d["sources"]),2)
            self.assertGreaterEqual(d["preferred_ring"],2)
            self.assertLessEqual(d["preferred_ring"],8)
        self.assertIn("genetics",BY_DOMAIN)
        self.assertIn("mind_medicine",BY_DOMAIN)
        self.assertFalse(result["authority"]["external_posting"])

    def test_research_areas_include_all_requested_fields(self):
        names=" ".join(d.title+" "+d.scope for d in DOMAINS).lower()
        for term in ("genetiikka","psykologia","psykiatria","farmakologia",
                     "filosofia","geopolitiikka","talous","tekoäly","ilmasto"):
            self.assertIn(term,names)
        self.assertTrue(all(s.publisher and s.description for s in SOURCES))
        self.assertTrue(all(_query_url(s).startswith("https://") for s in SOURCES))
        self.assertGreaterEqual(len({s.publisher for s in SOURCES}),5)

    def test_rss_parses_news_and_stanford_philosophy(self):
        bbc=b"""<rss version="2.0"><channel><item><title>Economy &amp; labor</title>
          <link>https://www.bbc.com/news/articles/test-123</link>
          <description>&lt;b&gt;Latest headline&lt;/b&gt; and context</description>
          </item><item><title>Bad</title><link>http://localhost/private</link>
          <description>Reject</description></item></channel></rss>"""
        rows=_rss_docs(bbc,BY_SOURCE["bbc-business"])
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["courier_id"],27)
        self.assertEqual(rows[0]["title"],"Economy & labor")
        self.assertIn("Latest headline",rows[0]["summary"])
        sep=b"""<rss version="2.0"><channel><item><title>Metaphysics</title>
        <link>https://plato.stanford.edu/entries/metaphysics/</link>
        <description>Revised entry</description></item></channel></rss>"""
        self.assertEqual(_rss_docs(sep,BY_SOURCE["stanford-philosophy"])[0]["courier_id"],71)
        with self.assertRaises(ValueError):_rss_docs(b"<!DOCTYPE foo><rss/>",BY_SOURCE["bbc-world"])

    def test_arxiv_http_article_canonicalized_only_from_known_host(self):
        atom=b"""<feed xmlns="http://www.w3.org/2005/Atom">
        <entry><title>Genomic modelling</title>
        <link href="http://arxiv.org/abs/2611.12345v1"/>
        <summary>Test evidence</summary></entry>
        <entry><title>Internal</title><link href="http://127.0.0.1/admin"/>
        <summary>Bad</summary></entry></feed>"""
        records=_rss_docs(atom,BY_SOURCE["genomics-arxiv"])
        self.assertEqual(len(records),1)
        self.assertEqual(records[0]["url"],"https://arxiv.org/abs/2611.12345v1")
        self.assertEqual(records[0]["courier_id"],55)
        with self.assertRaises(ValueError):
            validate_records([{**records[0],"url":"http://arxiv.org/abs/2611.12345v1"}])

    def test_europepmc_parses_bounded_article_ids_and_rejects_external_links(self):
        data={"resultList":{"result":[
            {"source":"MED","id":"39444000","title":"Psychopharmacology trial",
             "abstractText":"<p>Prospective clinical study</p>", "firstPublicationDate":"2026-11-10"},
            {"source":"MED","id":"../../secrets","title":"Invalid","abstractText":"Bad"},
            {"source":"bogus","id":"12","title":"Bad","abstractText":"Bad"}]}}
        rows=_pmc_docs(json.dumps(data).encode(),BY_SOURCE["pharmacology-pmc"])
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["url"],"https://europepmc.org/article/MED/39444000")
        self.assertEqual(rows[0]["courier_id"],11)
        self.assertIn("Prospective clinical study",rows[0]["summary"])
        with self.assertRaises(ValueError):_pmc_docs(b'{"hello":true}',BY_SOURCE["pharmacology-pmc"])

    def test_fixed_url_queries_and_no_arbitrary_target(self):
        self.assertIn("search_query=cat%3Aq-bio.GN",_query_url(BY_SOURCE["genomics-arxiv"]))
        self.assertIn("format=json",_query_url(BY_SOURCE["ancient-dna-pmc"]))
        self.assertIn("pageSize=6",_query_url(BY_SOURCE["ancient-dna-pmc"]))
        self.assertIn("plato.stanford.edu/rss/sep.xml",_query_url(BY_SOURCE["stanford-philosophy"]))
        with self.assertRaises(ValueError):fetch_source("https://127.0.0.1/private")
        with self.assertRaises(ValueError):fetch_source("made-up-source")

    def test_ingest_denies_unapproved_urls_courier_mismatch_and_extra_authority(self):
        valid=paper("genomics-arxiv")
        cases=(
            {"courier_id":71},{"url":"http://arxiv.org/abs/2611.10001"},
            {"url":"https://127.0.0.1/"},{"url":"https://arxiv.org@localhost/abs/123"},
            {"url":"https://europepmc.org/article/MED/123"},
            {"source_id":"unknown"},{"classification":"sealed"},
            {"approved_for_posting":True},{"url":"https://arxiv.org/abs/123#frag"},
        )
        for case in cases:
            with self.subTest(case=case):
                with self.assertRaises(ValueError):validate_records([{**valid,**case}])
        with self.assertRaises(ValueError):validate_records([valid,valid])

    def test_balancing_all_sources_preserves_all_eight_fields(self):
        items=[]
        for source in SOURCES:
            items.extend(paper(source.id,str(i)) for i in range(6))
        selected=balanced_selection(items)
        self.assertEqual(len(selected),48)
        self.assertEqual({BY_SOURCE[r["source_id"]].domain for r in selected},set(BY_DOMAIN))
        for d in DOMAINS:
            self.assertEqual(sum(BY_SOURCE[x["source_id"]].domain==d.id for x in selected),6)
        self.assertEqual(selected,balanced_selection(items))
        with self.assertRaises(ValueError):balanced_selection(items,limit=1000)

    def test_auto_route_reuses_specialist_rings_and_marks_unknown(self):
        records=[paper("genomics-arxiv"),paper("psychiatry-pmc","2"),
                 paper("arxiv-econ","3"),paper("stanford-philosophy","4")]
        report=plan(records)
        self.assertEqual(report["schema_version"],2)
        self.assertEqual(len(report["packets"]),4)
        self.assertEqual({p["target_ring"] for p in report["packets"]},{2,3,4,5})
        for packet in report["packets"]:
            self.assertEqual(len(packet["specialist_ideas"]),8)
            self.assertEqual(len({i["member_id"] for i in packet["specialist_ideas"]}),8)
            expected={m["id"] for m in catalog()["members"] if m["ring"]==packet["target_ring"]}
            self.assertEqual({i["member_id"] for i in packet["specialist_ideas"]},expected)
            for idea in packet["specialist_ideas"]:
                self.assertEqual(len(idea["simulated_modulators"]),6)
                self.assertIn("curiosity",idea["simulated_affect"])
                self.assertFalse(idea["execution_enabled"])
                self.assertFalse(idea["evidence_authenticated"])
            self.assertFalse(packet["truth_verified"])
            self.assertFalse(packet["publication_enabled"])
            self.assertFalse(packet["independent_sources_verified"])
            self.assertTrue(packet["human_review_required"])
            self.assertTrue(packet["reference_urls"])
        self.assertFalse(report["authority"]["external_posting"])
        step=report["council_session"]["request"]["steps"][0]
        self.assertEqual(len(step["observations"]),4)
        self.assertTrue(all(x["stance"]=="unknown" for x in step["observations"]))
        self.assertTrue(all(x["classification"]=="public" for x in step["observations"]))

    def test_explicit_ring_override_is_deterministic_and_non_authoritative(self):
        docs=[paper("genomics-arxiv"),paper("psychiatry-pmc","2")]
        a=plan(docs,ring_id=6,question="Onko selitys toistettavissa?")
        b=plan(docs,ring_id=6,question="Onko selitys toistettavissa?")
        self.assertEqual(a,b)
        self.assertEqual(len(a["packets"]),1)
        self.assertEqual(a["packets"][0]["target_ring"],6)
        self.assertEqual(a["packets"][0]["question"],"Onko selitys toistettavissa?")
        self.assertEqual(a["packets"][0]["steward_id"],61)
        with self.assertRaises(ValueError):plan(docs,ring_id=9)
        with self.assertRaises(ValueError):plan(docs,question="x"*381)

    def test_api_catalog_and_planning_never_fetch_or_publish(self):
        with patch("klone.limbo_atlas.fetch_source") as fetcher:
            a=self.client.get("/api/limbo-atlas/catalog")
            self.assertEqual(a.status_code,200)
            self.assertEqual(len(a.json()["domains"]),8)
            self.assertEqual(len(a.json()["sources"]),26)
            b=self.client.post("/api/limbo-atlas/plan",json={
                "observations":[paper("genomics-arxiv")],"target_ring":6,
                "research_question":"Mitä pitäisi tutkia?"})
            self.assertEqual(b.status_code,200,b.text[:400])
            self.assertEqual(b.json()["packets"][0]["target_ring"],6)
            fetcher.assert_not_called()
            for change in ({"target_ring":9},{"approved":True}):
                invalid=self.client.post("/api/limbo-atlas/plan",json={
                    "observations":[paper("genomics-arxiv")],**change})
                self.assertEqual(invalid.status_code,422)
            bad=self.client.post("/api/limbo-atlas/plan",json={
                "observations":[{**paper("genomics-arxiv"),"source_id":"unknown"}]})
            self.assertEqual(bad.status_code,422)

    def test_mobile_dashboard_has_safe_dom_and_legacy_arxiv_mapping(self):
        response=self.client.get("/limbo-atlas")
        self.assertEqual(response.status_code,200)
        self.assertIn('lang="fi"',response.text)
        for target in ('id="atlas-import"','id="atlas-ring"',
                       'id="atlas-plan"','id="atlas-packets"',
                       "genetiikka","farmakologia","filosofia"):
            self.assertIn(target,response.text)
        js=self.client.get("/static/limbo-atlas.js")
        self.assertEqual(js.status_code,200)
        self.assertIn('"arxiv-ai":"atlas-arxiv-ai"',js.text)
        self.assertIn('"arxiv-neuro":"neuro-arxiv"',js.text)
        self.assertIn('"/api/limbo-atlas/plan"',js.text)
        self.assertIn("specialist_ideas",js.text)
        self.assertIn("Simuloitu tila",js.text)
        self.assertIn("textContent",js.text)
        self.assertNotIn("innerHTML",js.text)
        self.assertNotIn('fetch("https:',js.text)

    def test_cli_manual_fetch_and_fail_closed_empty(self):
        with self.assertRaises(SystemExit):main(["--source","genomics-arxiv","--output","/tmp/fail.json"])
        with patch("klone.limbo_atlas.fetch_source",return_value=[paper("genomics-arxiv")]),\
             patch("klone.limbo_atlas.write_new_report") as out:
            self.assertEqual(main(["--fetch","--source","genomics-arxiv",
                                   "--output","/tmp/atlas-mocked.json"]),0)
            out.assert_called_once()
            report=json.loads(out.call_args.args[1])
            self.assertEqual(len(report["observations"]),1)
            self.assertFalse(report["authority"]["external_posting"])
        with patch("klone.limbo_atlas.fetch_source",side_effect=ValueError("HTTP 503")):
            with self.assertRaises(SystemExit) as context:
                main(["--fetch","--domain","genetics","--output","/tmp/none.json"])
            self.assertIn("HTTP 503",str(context.exception))


if __name__=="__main__":
    unittest.main()
