"""Atlas E6 research intelligence: source boundary, reproducibility, grounded questions."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from klone.api import get_repository
from klone.limbo_atlas import BY_SOURCE, BY_DOMAIN
from klone.limbo_memory import ingest
from klone.limbo_memory_bridge import bridge
from klone.limbo_intelligence import analyze, main
from klone.main import create_app
from klone.repository import KloneRepository


def paper(source_id, code, title, abstract):
    spec=BY_SOURCE[source_id]
    if spec.kind=="arxiv":url="https://arxiv.org/abs/2611."+str(code)
    elif spec.kind=="europepmc":url="https://europepmc.org/article/MED/"+str(code)
    elif spec.publisher=="stanford":url="https://plato.stanford.edu/entries/ancestry-"+str(code)+"/"
    else:url="https://www.bbc.com/news/articles/test-"+str(code)
    return {
        "source_id":source_id,"courier_id":BY_DOMAIN[spec.domain].courier,
        "url":url,"title":title,"summary":abstract,"published_at":"2026-11-16",
    }


class E6ResearchTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.atlas=self.root/"atlas-memory.sqlite3"
        self.klone=self.root/"memory-core.sqlite3"
        self.repository=KloneRepository(self.klone)
        self.repository.initialize()
        self.docs=[
            paper("genomics-arxiv","26111",
                  "Ancestry markers in northern populations",
                  "Ancestry markers is associated with risk in northern populations."),
            paper("ancient-dna-pmc","26112",
                  "Ancestry markers in northern populations",
                  "Ancestry markers not associated with risk in northern populations."),
            paper("stanford-philosophy","26113",
                  "Ancestry evidence and ethical interpretation",
                  "Ethical analysis of ancestry interpretations and evidence."),
            paper("psychiatry-pmc","26114",
                  "Genetic ancestry and psychological interpretation",
                  "Psychological outcomes are difficult to interpret from genetic ancestry."),
            paper("arxiv-econ","26115",
                  "Financial institutions and employment",
                  "Economic outcomes in labor markets."),
        ]
        ingest(self.atlas,self.docs,root=self.root)
        bridge(self.atlas,self.klone,root=self.root,commit=True)

    def test_research_uses_real_memory_core_and_cites_sources(self):
        report=analyze(self.klone,"ancestry",limit=24)
        self.assertEqual(report["kind"],"klone-atlas-e6-research-intelligence")
        self.assertEqual(report["public_research_memory_count"],5)
        self.assertGreaterEqual(report["matched_memory_count"],3)
        self.assertTrue(all(x["source_url"].startswith("https://")
                            for x in report["memories"]))
        self.assertTrue(all(x["epistemic_status"]=="unverified_publisher_claim"
                            for x in report["memories"]))
        self.assertFalse(report["authority"]["memory_write"])
        self.assertFalse(report["authority"]["private_memory_access"])
        self.assertFalse(report["authority"]["automatic_approval"])
        self.assertIsNotNone(report["council72_preview"])
        self.assertEqual(report["council72_preview"]["epistemic_status"],
                         "unverified_publisher_reports")
        self.assertTrue(report["council72_preview"]["packets"])
        self.assertFalse(report["council72_preview"]["authority"]["automatic_approval"])

    def test_possible_tension_is_not_claimed_verified_contradiction(self):
        r=analyze(self.klone,"ancestry")
        self.assertTrue(any(x["kind"]=="potential_claim_tension" for x in r["comparisons"]))
        self.assertTrue(all(x["contradiction_verified"] is False for x in r["comparisons"]))
        self.assertTrue(all(x["independent_evidence_verified"] is False for x in r["comparisons"]))
        self.assertTrue(any(x["different_publishers"] for x in r["comparisons"]))

    def test_repeated_run_replay_deterministic_and_readonly(self):
        before=self.klone.read_bytes()
        a=analyze(self.klone,"ancestry")
        b=analyze(self.klone,"ancestry")
        self.assertEqual(a,b)
        self.assertEqual(before,self.klone.read_bytes())

    def test_specialists_use_existing_members_and_only_ideation(self):
        r=analyze(self.klone,"ancestry",target_ring=6)
        self.assertTrue(r["research_drafts"])
        self.assertTrue(all(x["specialist_ring"]==6 for x in r["research_drafts"]))
        self.assertTrue(all(len(x["specialist_member_ids"])==8 for x in r["research_drafts"]))
        self.assertTrue(all(x["state"]=="not_executed_research_proposal"
                            for x in r["research_drafts"]))
        self.assertTrue(all(len(p["specialist_ideas"])==8
                            for p in r["council72_preview"]["packets"]))
        self.assertTrue(all(not p["truth_verified"]
                            for p in r["council72_preview"]["packets"]))
        self.assertFalse(r["authority"]["external_posting"])

    def test_latest_version_and_history_count_kept(self):
        old=self.docs[0]
        revised={**old,"summary":"Ancestry markers not associated with risk in northern populations."}
        ingest(self.atlas,[revised],root=self.root)
        bridge(self.atlas,self.klone,root=self.root,commit=True)
        r=analyze(self.klone,"ancestry")
        a=[x for x in r["memories"] if x["source_id"]=="genomics-arxiv"]
        self.assertEqual(len(a),1)
        self.assertEqual(a[0]["version"],2)
        self.assertEqual(a[0]["version_count_in_core"],2)
        self.assertEqual(r["public_research_memory_count"],5)

    def test_deny_incorrect_input_and_empty_results(self):
        for q in ("","xy","x"*161):
            with self.subTest(q=q):
                with self.assertRaises(ValueError):analyze(self.klone,q)
        for size in (0,49,True):
            with self.assertRaises(ValueError):analyze(self.klone,"ancestry",limit=size)
        for ring in (1,9,False):
            with self.assertRaises(ValueError):analyze(self.klone,"ancestry",target_ring=ring)
        empty=analyze(self.klone,"unfindablewordxyz")
        self.assertEqual(empty["matched_memory_count"],0)
        self.assertEqual(empty["research_drafts"],[])
        self.assertIsNone(empty["council72_preview"])

    def test_only_public_research_room_is_read(self):
        with self.repository.connection() as conn:
            self.repository.upsert_memory_event({
                "room_id":"sealed-room","classification_level":"sealed",
                "event_type":"private_secret",
                "source_table":"secret_source","source_record_id":"abc",
                "occurred_at":"2026-11-16T00:00:00+00:00",
                "recorded_at":"2026-11-16T00:00:00+00:00",
                "title":"topsecret_keyword",
                "evidence_text":"private content",
            },conn=conn)
        report=analyze(self.klone,"topsecret_keyword")
        self.assertEqual(report["matched_memory_count"],0)
        self.assertEqual(report["public_research_memory_count"],5)

    def test_http_research_api_has_no_writes_and_422_on_invalid(self):
        app=create_app()
        app.dependency_overrides[get_repository]=lambda:self.repository
        client=TestClient(app)
        before=self.klone.read_bytes()
        resp=client.get("/api/limbo-atlas/intelligence",params={"q":"ancestry"})
        self.assertEqual(resp.status_code,200,resp.text[:450])
        self.assertEqual(resp.json()["kind"],"klone-atlas-e6-research-intelligence")
        self.assertEqual(self.klone.read_bytes(),before)
        resp=client.get("/api/limbo-atlas/intelligence",params={"q":"bad","ring":9})
        self.assertEqual(resp.status_code,422)

    def test_cli_research_report_is_offline_and_deterministic(self):
        path=self.root/"research-report.json"
        with patch("klone.limbo_intelligence.write_new_report") as write:
            self.assertEqual(main(["--klone-db",str(self.klone),
                                   "--question","ancestry","--output",str(path)]),0)
            self.assertIn('"comparisons"',write.call_args.args[1])
            self.assertIn('"research_drafts"',write.call_args.args[1])


if __name__=="__main__":
    unittest.main()
