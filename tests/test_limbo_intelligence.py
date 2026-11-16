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

    def test_finnish_search_uses_explicit_aliases(self):
        result=analyze(self.klone,"genetiikka")
        self.assertGreaterEqual(result["matched_memory_count"],1)
        self.assertIn("genetics",result["domain_counts"])
        philosophy=analyze(self.klone,"filosofia")
        self.assertGreaterEqual(philosophy["matched_memory_count"],1)
        self.assertFalse(philosophy["authority"]["memory_write"])

    def test_mobile_ui_contains_e6_controls_and_safe_dom(self):
        from klone.main import create_app
        with TestClient(create_app()) as client:
            page=client.get("/limbo-atlas")
            script=client.get("/static/limbo-atlas.js")
        self.assertEqual(page.status_code,200)
        self.assertIn('id="atlas-e6-form"',page.text)
        self.assertIn('id="atlas-e6-ring"',page.text)
        self.assertEqual(script.status_code,200)
        self.assertIn('"/api/limbo-atlas/intelligence?q="',script.text)
        self.assertIn("council72_preview",script.text)
        self.assertNotIn("innerHTML",script.text)

    def test_main_readonly_canary_has_no_mutating_routes(self):
        import os
        from klone.limbo_main_research_canary import app as canary
        with patch.dict(os.environ,{"KLONE_MAIN_RESEARCH_DB":str(self.klone)}):
            client=TestClient(canary)
            health=client.get("/health")
            self.assertEqual(health.status_code,200)
            self.assertTrue(health.json()["read_only"])
            self.assertEqual(health.json()["room_scope"],"research-room")
            before=self.klone.read_bytes()
            response=client.get("/api/limbo-atlas/intelligence",params={"q":"genetiikka"})
            self.assertEqual(response.status_code,200,response.text[:400])
            self.assertGreaterEqual(response.json()["matched_memory_count"],1)
            other=client.get("/api/limbo-atlas/memory/recall",params={"q":"genetics"})
            self.assertEqual(other.status_code,200,other.text[:300])
            self.assertEqual(client.post("/api/limbo-atlas/intelligence",json={}).status_code,405)
            self.assertEqual(client.post("/api/memory/events",json={}).status_code,404)
            self.assertEqual(before,self.klone.read_bytes())

    def test_termux_upgrade_scripts_parse_as_bash(self):
        import shutil,subprocess
        shell=shutil.which("bash")
        if not shell:
            self.skipTest("bash not installed on this test runner")
        root=Path(__file__).resolve().parents[1]
        for name in ("klone-atlas-e3-phone.sh","klone-main-research-canary.sh",
                     "klone-atlas-main-memory.sh"):
            with self.subTest(name=name):
                result=subprocess.run([shell,"-n",str(root/"scripts"/name)],
                                      capture_output=True,text=True,timeout=10)
                self.assertEqual(result.returncode,0,result.stderr)

    def test_sidecar_launcher_never_restarts_main_service(self):
        script=(Path(__file__).resolve().parents[1]/
            "scripts"/"klone-main-research-canary.sh").read_text(encoding="utf-8")
        self.assertIn("127.0.0.1:8000/api/health",script)
        self.assertIn("--port 8041",script)
        self.assertIn("klone.limbo_main_research_canary:app",script)
        self.assertNotIn("kill -",script)
        self.assertNotIn("git switch",script)
        self.assertNotIn("--commit",script)

    def test_main_bridge_requires_running_research_room_and_owner(self):
        script=(Path(__file__).resolve().parents[1]/
                "scripts"/"klone-atlas-main-memory.sh").read_text(encoding="utf-8")
        self.assertIn("/api/health",script)
        self.assertIn("/api/rooms",script)
        self.assertIn("research_room_ready",script)
        self.assertIn("PAAMUISTI",script)
        self.assertIn("PRAGMA integrity_check",script)
        self.assertIn("original.backup(destination",script)
        self.assertIn("--commit",script)
        self.assertNotIn("kill -",script)
        self.assertNotIn("git switch",script)

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
