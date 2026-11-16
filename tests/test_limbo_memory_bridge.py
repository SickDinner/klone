"""E5 regression: actual KLONE Memory Core bridge, no trust or rights escalation."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from klone.api import _resolve_rooms
from klone.guards import access_guard, classification_guard
from klone.limbo_memory import ingest as e3_ingest, status as e3_status
from klone.limbo_memory_bridge import ROOM, bridge, recall
from klone.limbo_atlas import BY_SOURCE, BY_DOMAIN
from klone.main import create_app
from klone.memory import MemoryService
from klone.repository import KloneRepository
from klone.rooms import room_registry


SOURCES=["genomics-arxiv","psychiatry-pmc","arxiv-econ","stanford-philosophy",
         "bbc-world","quantum-arxiv","atlas-arxiv-ai","bbc-health"]


def article(i):
    sid=SOURCES[i % len(SOURCES)]
    spec=BY_SOURCE[sid]
    if spec.kind=="arxiv":
        url="https://arxiv.org/abs/2611."+str(10000+i)
    elif spec.kind=="europepmc":
        url="https://europepmc.org/article/MED/"+str(38000000+i)
    elif spec.publisher=="stanford":
        url="https://plato.stanford.edu/entries/research-"+str(i)+"/"
    else:
        url="https://www.bbc.com/news/articles/research-"+str(i)
    return {
        "source_id":sid,"courier_id":BY_DOMAIN[spec.domain].courier,
        "url":url,"title":"Genetics and memory research "+str(i),
        "summary":"Unverified metadata entry, research methods and science.",
        "published_at":"2026-11-16",
    }


class AtlasE5BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.source=self.root/"atlas-memory.sqlite3"
        self.target=self.root/"klone-mission.sqlite3"
        self.repo=KloneRepository(self.target)
        self.repo.initialize()

    def ingest(self, docs):
        return e3_ingest(self.source,docs,root=self.root)

    def preview(self,**kwargs):
        return bridge(self.source,self.target,root=self.root,**kwargs)

    def query(self):
        return self.repo.list_memory_events(room_id=ROOM,limit=200,offset=0)

    def test_policies_keep_original_public_room_denied_and_research_room_explicit(self):
        original=access_guard.evaluate(room_id="public-room",
                                       actor_role="owner",requested_permission="write")
        self.assertNotEqual(original.decision,"allowed")
        research=room_registry.get_room(ROOM)
        self.assertEqual(research.classification,"public")
        self.assertEqual(research.status,"active")
        self.assertEqual(access_guard.evaluate(room_id=ROOM,actor_role="owner",
                          requested_permission="write").decision,"allowed")
        self.assertEqual(access_guard.evaluate(room_id=ROOM,actor_role="worker",
                          requested_permission="write").decision,"blocked")
        self.assertEqual(classification_guard.evaluate(
                         room_id=ROOM,classification_level="personal").decision,"blocked")
        self.assertEqual(_resolve_rooms(requested_room_id=ROOM,
                         permission="read")[0].id,ROOM)

    def test_preview_is_readonly_and_147_articles_bridge_to_core(self):
        self.ingest([article(i) for i in range(147)])
        before=self.target.read_bytes()
        preview=self.preview()
        self.assertEqual(preview["mode"],"preview")
        self.assertEqual(preview["new_events"],147)
        self.assertFalse(preview["memory_events_were_written"])
        self.assertEqual(self.target.read_bytes(),before)
        done=self.preview(commit=True)
        self.assertEqual(done["new_events"],147)
        self.assertEqual(done["already_present"],0)
        self.assertEqual(len(done["inserted_event_ids"]),147)
        self.assertEqual(len(self.query()),147)
        self.assertEqual(e3_status(self.source,root=self.root)["articles"],147)
        with self.repo.connection() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM memory_provenance "
                 "WHERE room_id=?", (ROOM,)).fetchone()[0],147)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM audit_events "
                 "WHERE room_id=? AND event_type='atlas_public_memory_import'",
                 (ROOM,)).fetchone()[0],1)

    def test_idempotent_repeat_import_has_no_new_events_or_audits(self):
        self.ingest([article(i) for i in range(4)])
        first=self.preview(commit=True)
        second=self.preview(commit=True)
        self.assertEqual(first["new_events"],4)
        self.assertEqual(second["new_events"],0)
        self.assertEqual(second["already_present"],4)
        self.assertEqual(len(self.query()),4)
        with self.repo.connection() as conn:
            self.assertEqual(conn.execute(
                 "SELECT COUNT(*) FROM audit_events WHERE room_id=?",
                 (ROOM,)).fetchone()[0],1)

    def test_new_version_gets_new_provenanced_event_without_rewriting_old(self):
        original=article(0)
        self.ingest([original])
        self.preview(commit=True)
        newer={**original,"summary":"Publisher metadata changed; still unverified."}
        self.ingest([newer])
        preview=self.preview()
        self.assertEqual(preview["new_events"],1)
        self.preview(commit=True)
        rows=self.query()
        self.assertEqual(len(rows),2)
        metadata=[json.loads(x["metadata_json"]) for x in rows]
        self.assertEqual({m["version"] for m in metadata},{1,2})
        self.assertTrue(all(m["truth_verified"] is False for m in metadata))
        self.assertEqual(len({x["source_record_id"] for x in rows}),2)

    def test_memory_core_context_and_provenance_are_visible_readonly(self):
        self.ingest([article(0)])
        self.preview(commit=True)
        record=self.query()[0]
        package=MemoryService(self.repo).assemble_context_package(
            room_id=ROOM,event_id=record["id"])
        self.assertEqual(package.room_id,ROOM)
        self.assertTrue(package.included_events)
        text=package.included_events[0].evidence_text
        self.assertIn("VAHVISTAMATON",text)
        prov=self.repo.list_memory_provenance(
            room_id=ROOM,owner_type="event",owner_id=str(record["id"]))
        self.assertEqual(len(prov),1)
        self.assertEqual(prov[0]["source_table"],"atlas_revisions")
        self.assertEqual(prov[0]["provenance_type"],"source_lineage")

    def test_audit_failure_rolls_back_memory_events_and_provenance(self):
        self.ingest([article(i) for i in range(4)])
        with patch("klone.limbo_memory_bridge.AuditService.log_event",
                   side_effect=OSError("audit sink unavailable")):
            with self.assertRaises(OSError):
                self.preview(commit=True)
        self.assertEqual(self.query(),[])
        with self.repo.connection() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM memory_provenance "
                    "WHERE room_id=?", (ROOM,)).fetchone()[0],0)
        self.assertEqual(self.preview()["new_events"],4)

    def test_security_guards_reject_unknown_room_or_missing_owner_write(self):
        self.ingest([article(0)])
        with patch("klone.limbo_memory_bridge.ROOM","sealed-room"):
            with self.assertRaises(PermissionError):
                bridge(self.source,self.target,root=self.root,commit=True)
        self.assertEqual(self.query(),[])
        with patch("klone.limbo_memory_bridge.access_guard.evaluate") as denial:
            denial.return_value=type("Denied",(),{"decision":"requires_approval"})()
            with self.assertRaises(PermissionError):
                self.preview(commit=True)

    def test_reject_uninitialized_target_symlinks_and_same_file(self):
        self.ingest([article(0)])
        missing=self.root/"non-existent.sqlite3"
        with self.assertRaises(ValueError):
            bridge(self.source,missing,root=self.root,commit=True)
        with self.assertRaises(ValueError):
            bridge(self.source,self.source,root=self.root,commit=True)
        target=self.root/"alternate.sqlite3"
        symlink=self.root/"symlink.sqlite3"
        symlink.symlink_to(self.target)
        with self.assertRaises(ValueError):
            bridge(self.source,symlink,root=self.root,commit=True)
        target.touch()
        with self.assertRaises(ValueError):
            bridge(self.source,target,root=self.root,commit=True)
        self.assertEqual(self.query(),[])

    def test_pagination_preview_and_import_with_tight_limit(self):
        self.ingest([article(i) for i in range(5)])
        first=self.preview(commit=True,offset=0,limit=2)
        self.assertEqual(first["new_events"],2)
        self.assertEqual(first["next_offset"],2)
        second=self.preview(commit=True,offset=2,limit=3)
        self.assertEqual(second["new_events"],3)
        self.assertIsNone(second["next_offset"])
        self.assertEqual(len(self.query()),5)
        for bad in (0,513,True,"40"):
            with self.subTest(limit=bad):
                with self.assertRaises(ValueError):
                    self.preview(limit=bad)

    def test_core_recall_is_cited_and_read_only(self):
        self.ingest([article(i) for i in range(6)])
        self.preview(commit=True)
        before=self.target.read_bytes()
        result=recall(self.target,"genetics",limit=3)
        self.assertEqual(result["kind"],"klone-atlas-e5-recall")
        self.assertEqual(len(result["results"]),3)
        self.assertTrue(all(x["epistemic_status"]=="unverified_publisher_claim"
                            for x in result["results"]))
        self.assertTrue(all(x["source_url"].startswith("https://")
                            for x in result["results"]))
        self.assertIn("research-room",result["results"][0]["memory_context_url"])
        self.assertEqual(before,self.target.read_bytes())
        with self.assertRaises(ValueError):recall(self.target," ")

    def test_atlas_e5_http_recall_is_readonly_and_cites_public_articles(self):
        self.ingest([article(0),article(1)])
        self.preview(commit=True)
        from klone.api import get_repository
        app=create_app()
        app.dependency_overrides[get_repository]=lambda:self.repo
        client=TestClient(app)
        before=len(self.query())
        result=client.get("/api/limbo-atlas/memory/recall",
                          params={"q":"genetics","limit":20})
        self.assertEqual(result.status_code,200,result.text[:400])
        payload=result.json()
        self.assertEqual(payload["kind"],"klone-atlas-e5-recall")
        self.assertEqual(len(payload["results"]),2)
        self.assertTrue(all(p["source_url"].startswith("https://") for p in payload["results"]))
        self.assertEqual(len(self.query()),before)
        bad=client.get("/api/limbo-atlas/memory/recall",params={"q":"g","limit":100})
        self.assertEqual(bad.status_code,422)

    def test_stored_public_abstracts_are_searchable_in_core(self):
        doc={**article(0),"title":"No mention of target keyword",
             "summary":"Specialized electrocephalography research"}
        self.ingest([doc])
        self.preview(commit=True)
        result=recall(self.target,"electrocephalography")
        self.assertEqual(len(result["results"]),1)
        self.assertEqual(result["results"][0]["source_id"],"genomics-arxiv")

    def test_actual_memory_api_lists_public_research_room_events(self):
        self.ingest([article(0)])
        self.preview(commit=True)
        # The FastAPI app normally boots its own KLONE DB through env config.
        # Patch its repository dependency to use the exact tested KLONE database.
        from klone.api import get_repository
        app=create_app()
        app.dependency_overrides[get_repository]=lambda:self.repo
        client=TestClient(app)
        response=client.get("/api/memory/events",params={"room_id":ROOM,"limit":10})
        self.assertEqual(response.status_code,200,response.text[:300])
        rows=response.json()
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["classification_level"],"public")
        self.assertEqual(rows[0]["metadata"]["epistemic_status"],"unverified_publisher_claim")


if __name__=="__main__":
    unittest.main()
