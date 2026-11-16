"""E4 Atlas queue: no documents missing, reproducible cross-ring batching."""
from collections import Counter
from contextlib import closing
from pathlib import Path
import json
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from klone.limbo_atlas import BY_DOMAIN, BY_SOURCE, main as atlas_main
from klone.limbo_memory import ingest, status
from klone.limbo_queue import manifest, plan_batch, main


SOURCES = (
    "bbc-world", "arxiv-econ", "atlas-arxiv-ai", "bbc-health",
    "genomics-arxiv", "quantum-arxiv", "psychiatry-pmc", "stanford-philosophy"
)


def paper(i):
    sid=SOURCES[i % len(SOURCES)]
    source=BY_SOURCE[sid]
    if source.kind=="arxiv":
        url="https://arxiv.org/abs/2611." + str(10000+i)
    elif source.kind=="europepmc":
        url="https://europepmc.org/article/MED/" + str(38000000+i)
    elif source.publisher=="stanford":
        url="https://plato.stanford.edu/entries/research-"+str(i)+"/"
    else:
        url="https://www.bbc.com/news/articles/test-"+str(i)
    return {
        "source_id":sid,"courier_id":BY_DOMAIN[source.domain].courier,
        "url":url,"title":"Public publication "+str(i),
        "summary":"Unknown scientific or press claim "+str(i),
        "published_at":"2026-11-15",
    }


class AtlasE4QueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.db=self.root / "atlas-memory.sqlite3"

    def fixture(self, n=147):
        ingest(self.db,[paper(i) for i in range(n)],root=self.root)
        return manifest(self.db,root=self.root)

    def test_147_articles_have_four_batches_no_drops(self):
        q=self.fixture()
        self.assertEqual(q["article_count"],147)
        self.assertEqual(q["batch_count"],4)
        self.assertEqual([b["size"] for b in q["batches"]],[48,48,48,3])
        self.assertEqual(sum(q["domains"].values()),147)
        article_ids=[id_ for b in q["batches"] for id_ in b["article_ids"]]
        self.assertEqual(len(article_ids),147)
        self.assertEqual(len(set(article_ids)),147)
        self.assertEqual({k for k,v in q["domains"].items() if v>0},
                         set(BY_DOMAIN))
        for b in q["batches"][:3]:
            self.assertEqual(set(b["domains"]),set(BY_DOMAIN))
        self.assertFalse(q["facts_verified"])
        self.assertFalse(q["authority"]["automatic_research_execution"])
        self.assertFalse(q["authority"]["private_memory_access"])

    def test_manifest_is_stable_without_database_writes(self):
        a=self.fixture()
        before=status(self.db,root=self.root)
        b=manifest(self.db,root=self.root)
        self.assertEqual(a,b)
        self.assertEqual(before,status(self.db,root=self.root))
        self.assertEqual(a["snapshot_sha256"],b["snapshot_sha256"])
        self.assertTrue(all(x["state"]=="unreviewed_queue_draft" for x in a["batches"]))

    def test_changed_article_revision_changes_snapshot_and_review_queue(self):
        old=self.fixture(18)
        changed=paper(8)
        changed["summary"]="This is an updated publisher abstract; claims remain unverified."
        delta=ingest(self.db,[changed,paper(19)],root=self.root)
        self.assertEqual(delta["counts"]["metadata_changed"],1)
        new=manifest(self.db,root=self.root)
        self.assertNotEqual(old["snapshot_sha256"],new["snapshot_sha256"])
        self.assertEqual(new["article_count"],19)
        self.assertEqual(len({id_ for b in new["batches"] for id_ in b["article_ids"]}),19)
        self.assertEqual(new["batch_count"],1)

    def test_batch_size_custom_and_reject_invalid_values(self):
        self.fixture(51)
        a=manifest(self.db,root=self.root,batch_size=20)
        self.assertEqual([x["size"] for x in a["batches"]],[20,20,11])
        for size in (0,-2,49,True,"24"):
            with self.subTest(size=size):
                with self.assertRaises(ValueError):
                    manifest(self.db,root=self.root,batch_size=size)

    def test_plan_one_batch_via_existing_council72_and_no_authority(self):
        data=self.fixture(50)
        with patch("klone.limbo_queue.plan", wraps=None) as research_plan:
            pass
        result=plan_batch(data,2,question="Miten vahvistamme havainnot?")
        self.assertEqual(result["kind"],"klone-atlas-e4-council-draft")
        self.assertEqual(result["batch_number"],2)
        self.assertEqual(result["size"],2)
        self.assertEqual(result["snapshot_sha256"],data["snapshot_sha256"])
        self.assertFalse(result["authority"]["automatic_approval"])
        self.assertEqual(result["review_status"],"not_reviewed")
        self.assertEqual(result["council"]["epistemic_status"],"unverified_publisher_reports")
        self.assertEqual(sum(len(step["observations"]) for step in result["council"]["council_session"]["request"]["steps"]),2)

    def test_ring_override_routes_to_one_specialist_ring(self):
        q=self.fixture(6)
        r=plan_batch(q,1,target_ring=6,question="Mikä voisi kumota hypoteesin?")
        self.assertEqual(len(r["council"]["packets"]),1)
        p=r["council"]["packets"][0]
        self.assertEqual(p["target_ring"],6)
        self.assertEqual(len(p["specialist_ideas"]),8)
        self.assertFalse(p["truth_verified"])
        self.assertFalse(p["publication_enabled"])

    def test_invalid_batch_and_non_manifest_rejected(self):
        q=self.fixture(1)
        for n in (0,2,True,-1,"1"):
            with self.subTest(n=n):
                with self.assertRaises(ValueError):plan_batch(q,n)
        with self.assertRaises(ValueError):plan_batch({"kind":"no"},1)
        with self.assertRaises(ValueError):plan_batch(q,1,target_ring=9)

    def test_archive_contains_incorrect_record_hash_then_fails_closed(self):
        self.fixture(1)
        with closing(sqlite3.connect(self.db)) as db:
            db.execute("UPDATE atlas_revisions SET record_sha256='bad' WHERE revision_id=1")
            db.commit()
        with self.assertRaises(ValueError):manifest(self.db,root=self.root)

    def test_invalid_record_host_or_courier_is_never_released(self):
        self.fixture(1)
        with closing(sqlite3.connect(self.db)) as db:
            db.execute("UPDATE atlas_articles SET courier_id=71 WHERE article_id=1")
            db.commit()
        with self.assertRaises(ValueError):manifest(self.db,root=self.root)

    def test_cli_export_manifest_is_new_file_and_no_network(self):
        self.fixture(3)
        out=self.root/"first-e4-queue.json"
        with patch("klone.limbo_queue._memory_path") as guard:
            # The same directory policy holds when root is supplied directly;
            # avoid CLI-specific env hacks in this isolated fixture.
            guard.side_effect=lambda p,root=None: self.db
            with patch("klone.limbo_queue.write_new_report") as writer:
                code=main(["--db",str(self.db),"--output",str(out)])
                self.assertEqual(code,0)
                report=json.loads(writer.call_args.args[1])
                self.assertEqual(report["article_count"],3)
                self.assertEqual(report["batch_count"],1)
                self.assertEqual(len(report["batches"][0]["observations"]),3)
                self.assertFalse(report["authority"]["external_actions"])

    def test_cli_batch_requires_existing_valid_number(self):
        q=self.fixture(3)
        with self.assertRaises(ValueError):
            plan_batch(q,2)

    def test_empty_finance_source_is_distinguished_from_network_error(self):
        from klone.limbo_atlas import BY_SOURCE
        finance="arxiv-finance"
        science="genomics-arxiv"
        with patch("klone.limbo_atlas.fetch_source",
                   side_effect=lambda sid: [] if sid==finance else [paper(4)]),\
             patch("klone.limbo_atlas.write_new_report") as writer:
            atlas_main(["--fetch","--source",finance,"--source",science,
                        "--output","/tmp/e4-empty-finance.json"])
            report=json.loads(writer.call_args.args[1])
            self.assertEqual(report["fetch_errors"],[])
            self.assertEqual(report["empty_sources"],[{"source_id":finance,"status":"empty"}])


if __name__ == "__main__":
    unittest.main()
