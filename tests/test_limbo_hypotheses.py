"""E7/E8 research contracts: versioned hypothesis provenance and cross-domain radar."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from klone.limbo_atlas import BY_DOMAIN, BY_SOURCE
from klone.limbo_memory import ingest
from klone.limbo_memory_bridge import bridge
from klone.limbo_hypotheses import create,attach,review,detail,list_hypotheses
from klone.limbo_discovery import radar,compare_snapshots
from klone.limbo_intelligence import analyze,_memories
from klone.repository import KloneRepository


def paper(sid,code,title,summary):
    source=BY_SOURCE[sid]
    if source.kind=="arxiv":
        url="https://arxiv.org/abs/2611."+str(code)
    elif source.kind=="europepmc":
        url="https://europepmc.org/article/MED/"+str(code)
    elif source.publisher=="stanford":
        url="https://plato.stanford.edu/entries/test-"+str(code)+"/"
    else:
        url="https://www.bbc.com/news/articles/test-"+str(code)
    return {"source_id":sid,"courier_id":BY_DOMAIN[source.domain].courier,
            "url":url,"title":title,"summary":summary,
            "published_at":"2026-11-16"}


class E7E8Tests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.archive=self.root/"atlas-memory.sqlite3"
        self.core=self.root/"klone-core.sqlite3"
        self.journal=self.root/"atlas-hypotheses.sqlite3"
        KloneRepository(self.core).initialize()
        self.documents=[
            paper("genomics-arxiv",15230,"Genetic memory markers in populations",
                  "Genetic markers correlate with recorded memory differences."),
            paper("psychiatry-pmc",15231,"Genetic memory markers in patients",
                  "Genetic markers do not correlate with recorded memory differences."),
            paper("ancient-dna-pmc",15232,"Genetic memory markers in ancient DNA",
                  "Ancient DNA comparisons and population genetic memory markers."),
            paper("stanford-philosophy",15233,"Genetic memory interpretation and ethics",
                  "Philosophical interpretation of genetic memory markers."),
            paper("bbc-business",15234,"Financial employment outcomes",
                  "Economic evidence of employment outcomes."),
        ]
        ingest(self.archive,self.documents,root=self.root)
        bridge(self.archive,self.core,commit=True,root=self.root)
        self.core_before=self.core.read_bytes()
        self.sources={x["source_id"]:x for x in _memories(self.core)}

    def _proposal(self,commit=True,title="Ancestry markers and memory"):
        return create(self.journal,self.core,title=title,domain="genetics",
                      question="Do genetic markers predict memory differences?",
                      falsifier="Independent pre-registered populations show no association.",
                      commit=commit,root=self.root)

    def _attach(self,hid,source,stance,revision,commit=True):
        return attach(self.journal,self.core,hypothesis_id=hid,
                      source_event_id=self.sources[source]["event_id"],
                      stance=stance,note="Compare methods and replicate.",
                      expected_revision=revision,commit=commit,root=self.root)

    def test_owner_preview_never_writes_journal_or_core(self):
        result=self._proposal(commit=False)
        self.assertEqual(result["mode"],"preview")
        self.assertFalse(self.journal.exists())
        self.assertFalse(result["memory_write"])
        self.assertEqual(self.core.read_bytes(),self.core_before)

    def test_propose_attach_support_counter_and_review_append_only(self):
        p=self._proposal()
        hid=p["hypothesis_id"]
        self.assertEqual(p["revision"],1)
        a=self._attach(hid,"genomics-arxiv","support_candidate",1)
        b=self._attach(hid,"psychiatry-pmc","counter_candidate",2)
        self.assertEqual([a["revision"],b["revision"]],[2,3])
        preview=review(self.journal,hypothesis_id=hid,state="needs_replication",
                       notes="No full papers checked.",expected_revision=3,
                       commit=False,root=self.root)
        self.assertFalse(preview["memory_write"])
        self.assertEqual(detail(self.journal,hid,root=self.root)["revision"],3)
        result=review(self.journal,hypothesis_id=hid,state="needs_replication",
                      notes="No full papers checked.",expected_revision=3,
                      commit=True,root=self.root)
        self.assertEqual(result["revision"],4)
        history=detail(self.journal,hid,root=self.root,core_db=self.core)
        self.assertEqual(history["state"],"needs_replication")
        self.assertEqual(history["linked_sources"],2)
        self.assertEqual(len(history["publisher_groups"]),2)
        self.assertTrue(history["publisher_groups_not_independent_sources"])
        self.assertEqual(history["stance_counts"],
                         {"counter_candidate":1,"support_candidate":1})
        self.assertEqual(history["stale_source_event_ids"],[])
        self.assertEqual(history["events"][0]["event_type"],"proposed")
        self.assertTrue(all(e["event_hash"] for e in history["events"]))
        self.assertFalse(history["scientifically_verified"])
        self.assertEqual(self.core_before,self.core.read_bytes())

    def test_no_duplicate_source_and_concurrent_stale_revision(self):
        hid=self._proposal()["hypothesis_id"]
        self._attach(hid,"genomics-arxiv","context",1)
        with self.assertRaises(ValueError):
            self._attach(hid,"genomics-arxiv","counter_candidate",2)
        with self.assertRaises(ValueError):
            self._attach(hid,"psychiatry-pmc","context",1)
        with self.assertRaises(ValueError):
            review(self.journal,hypothesis_id=hid,state="in_review",
                   notes="test",expected_revision=1,commit=True,root=self.root)
        self.assertEqual(detail(self.journal,hid,root=self.root)["revision"],2)

    def test_tamper_detection_rejects_modified_history(self):
        hid=self._proposal()["hypothesis_id"]
        self._attach(hid,"genomics-arxiv","context",1)
        with closing(sqlite3.connect(self.journal)) as conn:
            conn.execute("UPDATE atlas_hypothesis_events SET payload_json='{}' "
                         "WHERE hypothesis_id=? AND revision=1",(hid,))
            conn.commit()
        with self.assertRaisesRegex(ValueError,"hash chain"):
            detail(self.journal,hid,root=self.root)
        with self.assertRaises(ValueError):
            review(self.journal,hypothesis_id=hid,state="in_review",
                   notes="review",expected_revision=2,commit=True,root=self.root)

    def test_reject_unverified_truth_promotion_private_or_fake_sources(self):
        hid=self._proposal()["hypothesis_id"]
        with self.assertRaises(ValueError):
            review(self.journal,hypothesis_id=hid,state="verified",
                   notes="not permitted",expected_revision=1,commit=True,root=self.root)
        with self.assertRaises(ValueError):
            self._attach(hid,"genomics-arxiv","scientifically_proven",1)
        with self.assertRaises(ValueError):
            attach(self.journal,self.core,hypothesis_id=hid,
                   source_event_id=999999,stance="support_candidate",note="fake",
                   expected_revision=1,commit=True,root=self.root)
        with self.assertRaises(ValueError):
            create(self.journal,self.core,title="X",domain="secret-room",
                   question="question",falsifier="wrong",commit=True,root=self.root)
        with self.assertRaises(ValueError):
            self._proposal(title="Ancestry markers and memory")
        self.assertEqual(self.core_before,self.core.read_bytes())

    def test_stale_core_source_identified_but_prior_event_preserved(self):
        hid=self._proposal()["hypothesis_id"]
        self._attach(hid,"genomics-arxiv","context",1)
        revised={**self.documents[0],"summary":
                 "Metadata updated with different source claims, not validated."}
        ingest(self.archive,[revised],root=self.root)
        bridge(self.archive,self.core,commit=True,root=self.root)
        snapshot=detail(self.journal,hid,root=self.root,core_db=self.core)
        self.assertEqual(len(snapshot["stale_source_event_ids"]),1)
        self.assertEqual(snapshot["revision"],2)
        self.assertFalse(snapshot["scientifically_verified"])

    def test_journal_list_and_symlink_path_fail_closed(self):
        self._proposal()
        x=list_hypotheses(self.journal,root=self.root)
        self.assertEqual(len(x["hypotheses"]),1)
        self.assertFalse(x["memory_write"])
        link=self.root/"link.sqlite3"
        link.symlink_to(self.journal)
        with self.assertRaises(ValueError):
            detail(link,1,root=self.root)

    def test_radar_discovers_cross_discipline_candidates_not_proof(self):
        report=radar(self.core,"genetiikka",limit=48)
        self.assertEqual(report["kind"],"klone-atlas-e8-discovery-radar")
        self.assertEqual(report["available_public_memories"],5)
        self.assertGreaterEqual(report["matched"],3)
        self.assertTrue(report["cross_discipline_candidates"])
        self.assertEqual(len(report["adversarial_research_lenses"]),8)
        for item in report["cross_discipline_candidates"]:
            self.assertEqual(len(item["domains"]),2)
            self.assertFalse(item["independent_studies_confirmed"])
            self.assertFalse(item["cross_domain_hypothesis_verified"])
        self.assertTrue(all("epistemic_debt" in x for x in report["attention_queue"]))
        self.assertFalse(report["authority"]["writes_memory"])
        self.assertEqual(self.core_before,self.core.read_bytes())
        self.assertEqual(report,radar(self.core,"genetiikka",limit=48))

    def test_radar_limits_and_no_private_memory(self):
        for limit in (0,1,97,True,"4"):
            with self.subTest(limit=limit):
                with self.assertRaises(ValueError):
                    radar(self.core,"genetiikka",limit=limit)
        for question in ("","x","x"*161):
            with self.assertRaises(ValueError):
                radar(self.core,question)
        report=radar(self.core,"financial",limit=24)
        self.assertEqual(report["selected"],1)
        self.assertEqual(report["cross_discipline_candidates"],[])

    def test_time_machine_distinguishes_selection_vs_actual_revision(self):
        a=analyze(self.core,"genetic",limit=24)
        b=analyze(self.core,"genetic",limit=2)
        diff=compare_snapshots(a,b)
        self.assertTrue(diff["missing_from_selection"])
        self.assertEqual(diff["changed_versions"],[])
        updated={**self.documents[0],"summary":"Changed metadata; not confirmed."}
        ingest(self.archive,[updated],root=self.root)
        bridge(self.archive,self.core,commit=True,root=self.root)
        c=analyze(self.core,"genetic",limit=24)
        delta=compare_snapshots(a,c)
        self.assertTrue(delta["changed_versions"])
        self.assertTrue(delta["read_only"])
        with self.assertRaises(ValueError):
            compare_snapshots(a,analyze(self.core,"employment"))

    def test_discovery_api_is_readonly_on_atlas_and_canary(self):
        import os
        from klone.api import get_repository
        from klone.main import create_app
        from klone.limbo_main_research_canary import app as canary
        app=create_app()
        app.dependency_overrides[get_repository]=lambda:KloneRepository(self.core)
        with TestClient(app) as client:
            before=self.core.read_bytes()
            good=client.get("/api/limbo-atlas/discovery",params={"q":"genetiikka","limit":48})
            self.assertEqual(good.status_code,200,good.text[:450])
            self.assertEqual(good.json()["kind"],"klone-atlas-e8-discovery-radar")
            bad=client.get("/api/limbo-atlas/discovery",params={"q":"genetiikka","limit":97})
            self.assertEqual(bad.status_code,422)
            self.assertEqual(self.core.read_bytes(),before)
        with patch.dict(os.environ,{"KLONE_MAIN_RESEARCH_DB":str(self.core)}):
            with TestClient(canary) as client:
                report=client.get("/api/limbo-atlas/discovery",params={"q":"genetiikka"})
                self.assertEqual(report.status_code,200,report.text[:400])
                self.assertEqual(report.json()["kind"],"klone-atlas-e8-discovery-radar")
                self.assertEqual(client.post("/api/limbo-atlas/discovery",json={}).status_code,405)
                self.assertEqual(self.core_before,self.core.read_bytes())

    def test_atlas_e7_e8_ui_is_safe_and_has_working_controls(self):
        from klone.main import create_app
        with TestClient(create_app()) as client:
            html=client.get("/limbo-atlas")
            js=client.get("/static/limbo-atlas.js")
        self.assertEqual(html.status_code,200)
        self.assertIn('id="atlas-e7-import"',html.text)
        self.assertIn('id="atlas-e8-form"',html.text)
        self.assertEqual(js.status_code,200)
        self.assertIn("klone-e7-hypothesis-list",js.text)
        self.assertIn('/api/limbo-atlas/discovery?q=',js.text)
        self.assertNotIn("innerHTML",js.text)

    def test_android_upgrade_scripts_parse_and_preserve_main_service(self):
        import shutil,subprocess
        shell=shutil.which("bash")
        if shell is None:
            self.skipTest("bash unavailable")
        scripts=Path(__file__).resolve().parents[1]/"scripts"
        for filename in ("klone-atlas-e7-e8-phone.sh",
                         "klone-main-research-e8-upgrade.sh",
                         "klone-main-research-canary.sh"):
            with self.subTest(script=filename):
                proc=subprocess.run([shell,"-n",str(scripts/filename)],
                    capture_output=True,text=True,timeout=10)
                self.assertEqual(proc.returncode,0,proc.stderr)
        upgrade=(scripts/"klone-main-research-e8-upgrade.sh").read_text(encoding="utf-8")
        self.assertIn("127.0.0.1:8000/api/health",upgrade)
        self.assertIn("klone-main-research-readonly",upgrade)
        self.assertIn("klone.limbo_main_research_canary:app",upgrade)
        self.assertIn("candidates)!=1",upgrade)
        self.assertNotIn("kill -9",upgrade)
        launcher=(scripts/"klone-atlas-e7-e8-phone.sh").read_text(encoding="utf-8")
        self.assertIn("--propose",launcher)
        self.assertNotIn(" --commit",launcher)
        self.assertIn("--klone-db",launcher)

    def test_cli_is_explicit_commit_and_no_automatic_writes(self):
        from klone.limbo_hypotheses import main as journal_cli
        with patch("klone.limbo_hypotheses.write_new_report") as writer:
            result=journal_cli(["--propose","--klone-db",str(self.core),
                "--journal-db",str(self.journal),"--title","Research question",
                "--domain","genetics","--question","Do markers correlate?",
                "--falsifier","A replication finds no association.",
                "--output",str(self.root/"preview.json")])
            self.assertEqual(result,0)
            self.assertFalse(self.journal.exists())
            self.assertIn('"mode": "preview"',writer.call_args.args[1])
        with self.assertRaises(SystemExit):
            journal_cli(["--commit","--list"])
        with self.assertRaises(SystemExit):
            journal_cli(["--list","--journal-db",str(self.journal)])


if __name__=="__main__":
    unittest.main()
