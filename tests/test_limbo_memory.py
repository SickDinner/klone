"""Atlas E3 isolated append-only SQLite public research memory contracts."""
from pathlib import Path
from contextlib import closing
import json
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from klone.limbo_atlas import BY_DOMAIN, BY_SOURCE, main as atlas_main
from klone.limbo_memory import ingest, import_report, main, status


def paper(source_id="genomics-arxiv", code="1", title="Test article"):
    s = BY_SOURCE[source_id]
    urls = {
        "arxiv": "https://arxiv.org/abs/2611.1000" + code,
        "europepmc": "https://europepmc.org/article/MED/12345" + code,
    }
    if s.kind in urls:
        url=urls[s.kind]
    else:
        url="https://www.bbc.com/news/articles/test" + code
    return {"source_id":source_id,
            "courier_id":BY_DOMAIN[s.domain].courier,
            "url":url,"title":title,"summary":"Public metadata, not verified research.",
            "published_at":"2026-11-15"}


class AtlasMemoryE3Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.db=self.root / "atlas-memory.sqlite3"

    def _ingest(self, papers):
        return ingest(self.db, papers, root=self.root)

    def _status(self):
        return status(self.db, root=self.root)

    def test_first_import_counts_every_article_and_dedupes_exact_replays(self):
        docs=[paper("genomics-arxiv","1"),
              paper("ancient-dna-pmc","2"),
              paper("psychiatry-pmc","3")]
        first=self._ingest(docs)
        self.assertEqual(first["status"],"archived")
        self.assertEqual(first["counts"],{"new":3,"metadata_changed":0,"unchanged":0})
        self.assertEqual(first["observations"],3)
        self.assertFalse(first["facts_verified"])
        self.assertFalse(first["external_actions"])
        self.assertEqual({x["domain"] for x in first["changes"]},{"genetics","mind_medicine"})
        replay=self._ingest(list(reversed(docs)))
        self.assertEqual(replay["status"],"already_imported")
        self.assertFalse(replay["memory_writes"])
        self.assertEqual(replay["run_id"],first["run_id"])
        summary=self._status()
        self.assertEqual((summary["runs"],summary["articles"],summary["revisions"]),(1,3,3))
        self.assertEqual({d["domain"] for d in summary["domains"]},{"genetics","mind_medicine"})

    def test_changed_abstract_is_new_version_but_not_verified_fact(self):
        original=paper()
        self._ingest([original])
        second={**original,"summary":"Updated publisher snippet is still not verified."}
        result=self._ingest([second])
        self.assertEqual(result["counts"],{"new":0,"metadata_changed":1,"unchanged":0})
        self.assertEqual(result["changes"][0]["version"],2)
        self.assertFalse(result["changes"][0]["evidence_authenticated"])
        again=self._ingest([original,paper("psychiatry-pmc","2")])
        self.assertEqual(again["counts"],{"new":1,"metadata_changed":1,"unchanged":0})
        self.assertEqual(again["changes"][0]["version"],3)
        summary=self._status()
        self.assertEqual(summary["runs"],3)
        self.assertEqual(summary["articles"],2)
        self.assertEqual(summary["revisions"],4)
        with closing(sqlite3.connect(self.db)) as conn:
            chain=conn.execute("SELECT r.version,r.previous_sha256,r.record_sha256 "
                               "FROM atlas_revisions r JOIN atlas_articles a ON r.article_id=a.article_id "
                               "WHERE a.source_id=? AND a.url=? ORDER BY r.version",
                               (original["source_id"],original["url"])).fetchall()
        self.assertIsNone(chain[0][1])
        self.assertEqual(chain[1][1],chain[0][2])
        self.assertEqual(chain[2][1],chain[1][2])

    def test_new_run_same_old_article_is_unchanged(self):
        old=paper();self._ingest([old])
        r=self._ingest([old,paper("genomics-arxiv","2")])
        self.assertEqual(r["counts"],{"new":1,"metadata_changed":0,"unchanged":1})
        self.assertEqual(self._status()["revisions"],2)

    def test_public_records_validation_is_atomic(self):
        self._ingest([paper()])
        before=self._status()
        bad_cases=[
            [paper("genomics-arxiv","2"),{**paper("genomics-arxiv","3"),"url":"http://arxiv.org/abs/2611.10003"}],
            [{**paper("genomics-arxiv","2"),"courier_id":24}],
            [paper(),paper()],
            [{**paper(),"source_id":"forged-private"}],
            [{**paper(),"title":""}],
            [{**paper(),"summary":"x"*361}],
        ]
        for items in bad_cases:
            with self.subTest(items=items):
                with self.assertRaises(ValueError):self._ingest(items)
                self.assertEqual(self._status(),before)

    def test_prevent_symlink_or_foreign_db_paths(self):
        foreign=self.root.parent / "not-our-public-memory.sqlite3"
        with self.assertRaises(ValueError):
            ingest(foreign,[paper()],root=self.root)
        outside=self.root / "nested" / "atlas-memory.sqlite3"
        with self.assertRaises(ValueError):
            ingest(outside,[paper()],root=self.root)
        target=self.root/"real-memory.sqlite3"
        target.touch()
        self.db.symlink_to(target)
        with self.assertRaises(ValueError):
            self._ingest([paper()])
        with self.assertRaises(ValueError):
            status(self.db,root=self.root)

    def test_all_147_observations_saved_without_council_truncation(self):
        # 26 sources * 6 hypothetical articles each; all must survive import.
        docs=[]
        for s in BY_SOURCE.values():
            for i in range(6):
                code=str(1000+len(docs))
                d=paper(s.id,code)
                if s.publisher == "stanford":
                    d["url"]="https://plato.stanford.edu/entries/test-"+code+"/"
                elif s.publisher == "guardian":
                    d["url"]="https://www.theguardian.com/world/2026/nov/15/test-"+code
                elif s.publisher == "smithsonian":
                    d["url"]="https://www.smithsonianmag.com/arts-culture/test-"+code+"/"
                elif s.publisher == "nasa":
                    d["url"]="https://www.nasa.gov/news-release/test-"+code+"/"
                docs.append(d)
        result=self._ingest(docs)
        self.assertEqual(result["observations"],156)
        self.assertEqual(result["counts"]["new"],156)
        self.assertEqual(self._status()["articles"],156)
        self.assertEqual(len(self._status()["domains"]),8)

    def test_ingest_report_only_e2_public_research(self):
        report={"kind":"klone-limbo-atlas-preview",
                "epistemic_status":"unverified_publisher_reports",
                "observations":[{**paper(),"receipt_sha256":"not_trusted",
                                 "publisher_group":"fake_authentication",
                                 "domain":"falsified"}]}
        file=self.root/"atlas-report.json"
        file.write_text(json.dumps(report),encoding="utf-8")
        result=import_report(self.db,file,root=self.root)
        self.assertEqual(result["counts"]["new"],1)
        self.assertEqual(result["changes"][0]["publisher_group"],"arxiv")
        file.write_text(json.dumps({**report,"kind":"klone-private-restricted"}),encoding="utf-8")
        with self.assertRaises(ValueError):
            import_report(self.db,file,root=self.root)
        self.assertEqual(self._status()["runs"],1)

    def test_memory_cli_needs_explicit_import_or_status(self):
        with self.assertRaises(SystemExit):
            main(["--db",str(self.db)])
        with self.assertRaises(SystemExit):
            main(["--status","--db",str(self.db)])

    def test_atlas_fetch_optional_memory_persists_all_in_batch(self):
        # The CLI is tested with a real temporary database and mocked network.
        # Its 48-item decision sample remains bounded, while memory gets 60.
        from klone.limbo_atlas import SOURCES
        docs=[]
        for i in range(60):
            source=SOURCES[i % len(SOURCES)]
            d=paper(source.id,str(i+1000))
            if source.publisher=="stanford":
                d["url"]="https://plato.stanford.edu/entries/test-"+str(i+1000)+"/"
            elif source.publisher=="guardian":
                d["url"]="https://www.theguardian.com/world/2026/nov/15/test-"+str(i+1000)
            elif source.publisher=="smithsonian":
                d["url"]="https://www.smithsonianmag.com/arts-culture/test-"+str(i+1000)+"/"
            elif source.publisher=="nasa":
                d["url"]="https://www.nasa.gov/news-release/test-"+str(i+1000)+"/"
            docs.append(d)
        # patch user-specific root only so production path checks still execute
        # in the temporary directory.
        def archive(db, items):
            self.assertEqual(len(items),60)
            return ingest(self.db,items,root=self.root)
        with patch("klone.limbo_atlas.fetch_source", side_effect=lambda sid:[d for d in docs if d["source_id"]==sid]),\
             patch("klone.limbo_memory.ingest",side_effect=archive) as mem,\
             patch("klone.limbo_atlas.time.sleep") as ignore_pause,\
             patch("klone.limbo_atlas.write_new_report") as write:
            self.assertEqual(atlas_main(["--fetch","--all","--memory-db",str(self.db),
                                         "--output","/tmp/atlas-e3-test.json"]),0)
            self.assertEqual(mem.call_count,1)
            self.assertEqual(self._status()["articles"],60)
            report=json.loads(write.call_args.args[1])
            self.assertEqual(len(report["observations"]),48)
            self.assertEqual(report["dropped_after_cap"],12)


if __name__=="__main__":
    unittest.main()
