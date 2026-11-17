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
from klone.limbo_source_dossiers import review_pair,review_all,_collapse_source_pairs,_publication_key,_source_class
from klone.limbo_intelligence import analyze,_memories
from klone.limbo_council_workbench import council_review,council_all
from klone.limbo_doctor import diagnose,_read_health
from klone.limbo_evidence_review import prepare,review_manifest,fill_template,main as evidence_main
from klone.limbo_evidence_candidates import suggest, main as candidate_main
from klone.limbo_evidence_accept import accept_context, main as accept_main
from klone.limbo_evidence_quality import audit_quality, main as quality_main
from klone.council72 import catalog
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
        from datetime import datetime
        for row in history["events"]:
            stamp=datetime.fromisoformat(row["payload"]["recorded_at"])
            self.assertIsNotNone(stamp.tzinfo)
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

    def test_single_field_query_explores_other_real_memory_domains(self):
        documents=[
            paper("genomics-arxiv",19224,
                  "Telomerase telomere maintenance in genetic material",
                  "Telomere maintenance assays for genomic stability."),
            paper("psychiatry-pmc",19225,
                  "Telomere maintenance in cellular ageing",
                  "Cellular ageing measurements test telomere maintenance."),
        ]
        ingest(self.archive,documents,root=self.root)
        bridge(self.archive,self.core,commit=True,root=self.root)
        original=self.core.read_bytes()
        report=radar(self.core,"telomerase",limit=24)
        self.assertEqual(report["matched"],1)
        self.assertEqual(report["selected"],1)
        self.assertEqual(report["discipline_coverage"],{"genetics":1})
        self.assertEqual(report["bridge_mode"],"cross_domain_expansion")
        self.assertGreater(report["outside_domain_documents_examined"],0)
        self.assertEqual(report["bridge_document_count"],1)
        self.assertEqual(report["bridge_documents"][0]["domain"],"mind_medicine")
        self.assertTrue(report["bridge_documents"][0]["source_url"].startswith("https://"))
        links=report["cross_discipline_candidates"]
        self.assertEqual(len(links),1)
        self.assertEqual(links[0]["candidate_origin"],"other_domain_public_memory")
        self.assertIn("telomere",links[0]["shared_terms"])
        self.assertIn("maintenance",links[0]["shared_terms"])
        self.assertFalse(links[0]["cross_domain_hypothesis_verified"])
        self.assertFalse(links[0]["independent_studies_confirmed"])
        self.assertEqual(self.core.read_bytes(),original)
        self.assertEqual(report,radar(self.core,"telomerase",limit=24))

    def test_e82_rejects_generic_word_soup_even_across_real_sources(self):
        noise=[
            paper("genomics-arxiv",19226,
                  "Telomerase perspectives contributions theory work",
                  "However potential results remain difficult, change historical past."),
            paper("psychiatry-pmc",19227,
                  "Perspectives contributions theory work",
                  "However potential results remain difficult, change historical past."),
        ]
        ingest(self.archive,noise,root=self.root)
        bridge(self.archive,self.core,commit=True,root=self.root)
        original=self.core.read_bytes()
        r=radar(self.core,"telomerase",limit=48)
        for pair in r["cross_discipline_candidates"]:
            # No E8.1 false link to the artificial boilerplate-only source.
            self.assertNotEqual(pair["second_event_id"],
                next(x["event_id"] for x in _memories(self.core)
                     if x["source_id"]=="psychiatry-pmc" and
                     x["title"]=="Perspectives contributions theory work"))
            self.assertNotIn("however",pair["shared_terms"])
            self.assertNotIn("potential",pair["shared_terms"])
            self.assertNotIn("perspectives",pair["shared_terms"])
            self.assertNotIn("contributions",pair["shared_terms"])
            self.assertNotIn("theory",pair["shared_terms"])
            self.assertTrue(pair["shared_title_concepts"])
            self.assertEqual(pair["quality_gate"],
                "e8.3-normalized-scientific-terms-v2")
        self.assertTrue(r["diagnostics"]["generic_topic_words_ignored"])
        self.assertTrue(r["diagnostics"]["shared_title_term_required_in_both_sources"])
        self.assertEqual(self.core.read_bytes(),original)

    def test_e82_detection_detecting_is_only_one_concept(self):
        from klone.limbo_discovery import _concepts
        self.assertEqual(_concepts(
            "However potential remain detecting detection difficult"),
            {"detection"})
        self.assertEqual(_concepts("telomere maintenance"),
                         {"telomere","maintenance"})

    def test_e83_real_device_false_positive_tokens_are_not_evidence(self):
        from klone.limbo_discovery import _concepts,BRIDGE_QUALITY_VERSION
        self.assertEqual(BRIDGE_QUALITY_VERSION,
                         "e8.3-normalized-scientific-terms-v2")
        self.assertEqual(_concepts("network networks"),{"network"})
        self.assertEqual(_concepts("graph graphs network networks"),
                         {"graph","network"})
        self.assertEqual(_concepts("detecting detection difficult"),{"detection"})
        self.assertEqual(_concepts("exploring under domains"),set())
        self.assertEqual(_concepts("agents agent"),{"agent"})
        self.assertEqual(_concepts("gene expression"),{"gene","expression"})
        self.assertNotIn("exploring",_concepts(
            "exploring sequencing under network networks"))

    def test_e83_real_device_weak_network_plural_link_is_rejected(self):
        samples=[
            paper("genomics-arxiv",19228,
                  "Graph networks in telomerase biology",
                  "We observe network networks under multiple conditions."),
            paper("psychiatry-pmc",19229,
                  "Network networks in behavioral medicine",
                  "Our results explore networks and network effects."),
            paper("stanford-philosophy",19230,
                  "Graph network structures in philosophy",
                  "Graph structure and network nodes across systems."),
        ]
        ingest(self.archive,samples,root=self.root)
        bridge(self.archive,self.core,commit=True,root=self.root)
        before=self.core.read_bytes()
        result=radar(self.core,"telomerase",limit=48)
        self.assertEqual(result["bridge_mode"],"cross_domain_expansion")
        ids={d["title"]:d["event_id"] for d in _memories(self.core)}
        self.assertNotIn(ids["Network networks in behavioral medicine"],
                         [p["second_event_id"] for p in result["cross_discipline_candidates"]])
        justified=[p for p in result["cross_discipline_candidates"]
                   if p["second_event_id"]==ids["Graph network structures in philosophy"]]
        self.assertEqual(len(justified),1)
        self.assertEqual(justified[0]["shared_terms"],["graph","network"])
        self.assertIn("manual verification",justified[0]["justification"])
        self.assertFalse(justified[0]["cross_domain_hypothesis_verified"])
        self.assertEqual(before,self.core.read_bytes())

    def test_zero_links_explains_missing_domain_and_suggests_followup(self):
        report=radar(self.core,"financial",limit=24)
        self.assertEqual(report["matched"],1)
        self.assertEqual(report["cross_discipline_candidates"],[])
        self.assertEqual(report["bridge_document_count"],0)
        self.assertGreater(report["outside_domain_documents_examined"],0)
        diagnostic=report["diagnostics"]
        self.assertEqual(diagnostic["matched_domain_count"],1)
        self.assertTrue(diagnostic["why_no_pairs"])
        self.assertTrue(diagnostic["suggested_next_queries"])
        self.assertTrue(diagnostic["no_links_does_not_mean_no_scientific_relation"])
        self.assertFalse(report["authority"]["writes_memory"])

    def test_query_with_no_memory_hits_does_not_invent_discovery(self):
        report=radar(self.core,"inventedunfindableterm",limit=24)
        self.assertEqual(report["matched"],0)
        self.assertEqual(report["selected"],0)
        self.assertEqual(report["bridge_documents"],[])
        self.assertEqual(report["cross_discipline_candidates"],[])
        self.assertIn("No query-matched",report["diagnostics"]["why_no_pairs"])

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

    def test_e9_dossier_uses_current_real_public_memory_sources(self):
        found=radar(self.core,"genetiikka")["cross_discipline_candidates"]
        self.assertTrue(found)
        pair=found[0]
        before=self.core.read_bytes()
        result=review_pair(self.core,pair["first_event_id"],pair["second_event_id"])
        self.assertEqual(result["kind"],"klone-atlas-e9-pair-dossier")
        self.assertEqual(result["concepts_in_both_titles"],pair["shared_title_concepts"])
        self.assertEqual(result["quality_gate"],pair["quality_gate"])
        self.assertTrue(result["source_a"]["source_url"].startswith("https://"))
        self.assertTrue(result["source_b"]["title"])
        self.assertTrue(result["source_a"]["receipt_sha256"])
        self.assertFalse(result["source_a"]["full_text_reviewed"])
        self.assertFalse(result["source_b"]["study_design_verified"])
        self.assertFalse(result["independence"]["independent_studies_confirmed"])
        self.assertFalse(result["scientific_truth_verified"])
        self.assertFalse(result["memory_write"])
        self.assertFalse(result["external_network_actions"])
        self.assertEqual(before,self.core.read_bytes())
        self.assertEqual(result,review_pair(
            self.core,pair["first_event_id"],pair["second_event_id"]))

    def test_e9_dossiers_reject_invalid_or_unselected_pairs(self):
        with self.assertRaises(ValueError):
            review_pair(self.core,1,1)
        with self.assertRaises(ValueError):
            review_pair(self.core,True,1)
        with self.assertRaises(ValueError):
            review_pair(self.core,999999,3)
        batch=review_all(self.core,question="genetiikka")
        self.assertEqual(batch["kind"],"klone-atlas-e9-review-batch")
        self.assertEqual(batch["candidate_count"],len(batch["dossiers"]))
        self.assertFalse(batch["memory_write"])
        self.assertTrue(all(not x["scientific_truth_verified"]
                            for x in batch["dossiers"]))
        self.assertEqual(self.core_before,self.core.read_bytes())

    def test_e91_deduplicates_real_device_agent_ssl_urls_not_memory_ids(self):
        # Actual Android issue: pair 90/9 and 90/58 references same
        # https://arxiv.org/abs/2611.17323v1 AgentSSL publication.
        docs={
            90:{"event_id":90,"source_url":"https://arxiv.org/abs/2611.11796v1"},
            9:{"event_id":9,"source_url":"https://arxiv.org/abs/2611.17323v1"},
            58:{"event_id":58,"source_url":"https://www.arxiv.org/abs/2611.17323v1"},
        }
        pairs=[{"first_event_id":90,"second_event_id":9},
               {"first_event_id":90,"second_event_id":58}]
        kept,duplicates=_collapse_source_pairs(pairs,docs)
        self.assertEqual(len(kept),1)
        self.assertEqual(kept[0]["duplicate_memory_event_pairs"],[[90,58]])
        self.assertEqual(duplicates[0]["canonical_event_ids"],[90,9])
        self.assertEqual(duplicates[0]["reason"],
                         "same_publication_pair_different_memory_events")
        self.assertEqual(_publication_key(docs[9]),_publication_key(docs[58]))

    def test_e91_canonical_id_does_not_merge_distinct_publications(self):
        docs={
            90:{"event_id":90,"source_url":"https://arxiv.org/abs/2611.11796v1"},
            9:{"event_id":9,"source_url":"https://arxiv.org/abs/2611.17323v1"},
            58:{"event_id":58,"source_url":"https://arxiv.org/abs/2611.17324v1"},
        }
        kept,duplicates=_collapse_source_pairs([
            {"first_event_id":90,"second_event_id":9},
            {"first_event_id":90,"second_event_id":58},
        ],docs)
        self.assertEqual(len(kept),2)
        self.assertEqual(duplicates,[])
        self.assertNotEqual(_publication_key(docs[9]),_publication_key(docs[58]))
        with self.assertRaises(ValueError):
            _publication_key({"source_url":"http://arxiv.org/abs/2611.11796"})

    def test_e91_news_is_not_independent_research_and_canonical_rss_params(self):
        news={"event_id":77,"source_url":
            "https://www.bbc.co.uk/news/articles/cmr4gxvrxd9yo?at_medium=RSS&at_campaign=rss"}
        canonical={"event_id":78,"source_url":
                   "https://bbc.co.uk/news/articles/cmr4gxvrxd9yo"}
        self.assertEqual(_publication_key(news),_publication_key(canonical))
        self.assertEqual(_source_class({"source_id":"bbc-science"})[0],
                         "news_or_reference_feed")
        self.assertEqual(_source_class({"source_id":"genomics-arxiv"})[0],
                         "research_preprint")
        self.assertEqual(_source_class({"source_id":"ancient-dna-pmc"})[0],
                         "indexed_research")
        batch=review_all(self.core,question="genetiikka")
        self.assertEqual(batch["raw_memory_pair_count"],
                         batch["candidate_count"]+batch["duplicate_memory_pair_count"])
        self.assertEqual(batch["schema_version"],2)
        self.assertTrue(all("source_comparison_type" in d for d in batch["dossiers"]))
        self.assertTrue(all(d["source_a"]["source_class"] and
                            d["source_b"]["source_class"] for d in batch["dossiers"]))
        self.assertEqual(batch["source_type_counts"]["research_metadata_pairs"]+
                         batch["source_type_counts"]["mixed_news_or_reference_pairs"],
                         batch["candidate_count"])
        self.assertFalse(batch["memory_write"])
        self.assertEqual(self.core_before,self.core.read_bytes())

    def test_e10_research_board_assigns_all_real_72_seats_without_votes(self):
        pair=review_all(self.core,question="genetiikka")["dossiers"][0]
        a=pair["source_a"]["event_id"]
        b=pair["source_b"]["event_id"]
        before=self.core.read_bytes()
        board=council_review(self.core,a,b)
        self.assertEqual(board["kind"],"klone-atlas-e10-council72-workbench")
        self.assertEqual(board["seat_count"],72)
        self.assertEqual(board["ring_count"],9)
        self.assertEqual(board["founder_count"],8)
        self.assertEqual(board["pending_review_count"],72)
        self.assertEqual(board["performed_review_count"],0)
        seats=board["assigned_seats"]
        self.assertEqual(len(seats),72)
        self.assertEqual(len({x["member_id"] for x in seats}),72)
        self.assertEqual(len({(x["ring"],x["slot"]) for x in seats}),72)
        self.assertEqual({x["member_id"] for x in seats},
                         {m["id"] for m in catalog()["members"]})
        founders=[x for x in seats if x["founder"]]
        self.assertEqual(sorted(x["oversees_ring"] for x in founders),list(range(1,9)))
        self.assertTrue(all(not x["vote_cast"] and not x["completed"]
                            and not x["permission_granted"] for x in seats))
        self.assertEqual(sum(x["assigned_seats"] for x in board["rings"]),72)
        self.assertTrue(all(not x["active_vote_count"] for x in board["rings"]))
        self.assertTrue(board["research_evidence_debt"])
        self.assertFalse(any(board["authority"].values()))
        self.assertTrue(board["source_summary"]["source_a"]["receipt_sha256"])
        self.assertEqual(board,council_review(self.core,b,a))
        self.assertEqual(board["report_sha256"],council_review(self.core,a,b)["report_sha256"])
        self.assertEqual(before,self.core.read_bytes())

    def test_e10_board_denies_forged_uncanonical_or_alias_pairs(self):
        with self.assertRaises(ValueError):
            council_review(self.core,1,1)
        with self.assertRaises(ValueError):
            council_review(self.core,True,2)
        with self.assertRaises(ValueError):
            council_review(self.core,999999,3)
        allboards=council_all(self.core,question="genetiikka",max_pairs=2)
        self.assertLessEqual(allboards["board_count"],2)
        self.assertEqual(allboards["total_pending_seat_assignments"],
                         allboards["board_count"]*72)
        self.assertFalse(any(allboards["authority"].values()))
        with self.assertRaises(ValueError):
            council_all(self.core,max_pairs=9)

    def test_e10_mixed_news_research_cannot_be_promoted_to_science(self):
        news=paper("bbc-science",22231,
                   "Genetic memory markers in genomic science",
                   "Genetic markers and memory may be correlated.")
        ingest(self.archive,[news],root=self.root)
        bridge(self.archive,self.core,commit=True,root=self.root)
        candidates=review_all(self.core,question="genetiikka")["dossiers"]
        mixed=[d for d in candidates if
               d["source_comparison_type"]=="mixed_news_or_reference_pair"]
        self.assertTrue(mixed)
        item=mixed[0]
        board=council_review(self.core,item["source_a"]["event_id"],
                             item["source_b"]["event_id"])
        self.assertIn("news_is_not_independent_study",
                      board["research_evidence_debt"])
        self.assertFalse(board["authority"]["hypothesis_verified"])

    def test_e10_doctor_validates_three_services_and_actual_db_without_writes(self):
        from klone import limbo_doctor
        before=self.core.read_bytes()
        healths={
            "main":{"status":"ok","app":"Klone",
                    "database_path":str(self.core),"app_version":"0.2.0"},
            "atlas":{"status":"ok","app":"Klone","app_version":"0.2.0"},
            "research":{"status":"ok","service":"klone-main-research-readonly",
                        "database_path":str(self.core),"read_only":True,
                        "feature_version":"E10"},
        }
        def mocked(url,*,opener=None):
            name=next(name for name,target in limbo_doctor.SERVICES
                      if url==target)
            return healths[name]
        with patch("klone.limbo_doctor._read_health",side_effect=mocked):
            result=diagnose(expected_main_db=self.core,
                            now="2026-11-17T00:00:00+00:00")
        self.assertEqual(result["kind"],"klone-e10-phone-doctor")
        self.assertEqual(result["health"],"ok")
        self.assertEqual(result["main_database"]["quick_check"],"ok")
        self.assertEqual(result["main_database"]["active_public_research_events"],5)
        self.assertEqual(result["services"]["research"]["main_db_matches"],True)
        self.assertEqual(result["problems"],[])
        self.assertFalse(any(result["safety"].values()))
        self.assertEqual(before,self.core.read_bytes())

    def test_e10_doctor_detects_mismatch_dead_sidecar_and_avoids_arbitrary_url(self):
        from klone import limbo_doctor
        before=self.core.read_bytes()
        def mocked(url,*,opener=None):
            if url.endswith(":8000/api/health"):
                return {"status":"ok","app":"Klone","database_path":str(self.core)}
            if url.endswith(":8041/health"):
                return {"status":"ok","service":"klone-main-research-readonly",
                        "database_path":str(self.root/"wrong.sqlite"),
                        "read_only":True,"feature_version":"E10"}
            raise OSError("connection refused")
        with patch("klone.limbo_doctor._read_health",side_effect=mocked):
            result=diagnose(expected_main_db=self.core)
        self.assertEqual(result["health"],"attention_required")
        self.assertIn("service_atlas_unavailable_or_invalid",result["problems"])
        self.assertIn("research_canary_database_mismatch",result["problems"])
        with self.assertRaises(ValueError):
            _read_health("https://example.org/do-not-fetch")
        self.assertEqual(before,self.core.read_bytes())

    def _e11_manifest(self):
        dossier=review_all(self.core,question="genetiikka")["dossiers"][0]
        first,second=dossier["source_a"]["event_id"],dossier["source_b"]["event_id"]
        manifest=prepare(self.core,first,second)
        manifest["sources"]["A"].update(
            text="Methods: We measured gene markers in a cohort. Results: Associations were reported.",
            owner_supplied=True,usage_rights_note="Owner-supplied excerpt for private review")
        manifest["sources"]["B"].update(
            text="Methods: We measured clinical markers. Results: No association was observed in patients.",
            owner_supplied=True,usage_rights_note="Owner-supplied excerpt for private review")
        return manifest

    def test_e11_owner_quotes_are_exact_cited_candidates_not_verified_facts(self):
        manifest=self._e11_manifest()
        manifest["annotations"]=[
            {"source":"A","claim_key":"gene-marker-link",
             "quote":"Associations were reported.",
             "stance":"support_candidate","note":"User suggests a positive candidate."},
            {"source":"B","claim_key":"gene-marker-link",
             "quote":"No association was observed in patients.",
             "stance":"counter_candidate","note":"User suggests a negative candidate."}]
        before=self.core.read_bytes()
        r=review_manifest(self.core,manifest)
        self.assertEqual(r["kind"],"klone-e11-offline-evidence-ledger")
        self.assertEqual(r["annotation_count"],2)
        self.assertEqual(len(r["opposing_annotation_candidates"]),1)
        self.assertEqual(r["opposing_annotation_candidates"][0]["status"],
                         "opposing_owner_annotations_not_verified_contradiction")
        self.assertEqual(r["quote_anchors"][0]["quote"],
                         "Associations were reported.")
        self.assertEqual(r["quote_anchors"][0]["char_start"],
                         manifest["sources"]["A"]["text"].index(
                             "Associations were reported."))
        self.assertFalse(r["quote_anchors"][0]["independently_verified"])
        self.assertFalse(r["council_state"]["approval"])
        self.assertTrue(all(not x for x in r["authority"].values()))
        self.assertEqual(r,review_manifest(self.core,manifest))
        self.assertEqual(before,self.core.read_bytes())
        self.assertNotIn("Methods: We measured",
                         json.dumps(r,ensure_ascii=False))

    def test_e11_rejects_fake_quotes_stale_sources_and_unapproved_content(self):
        m=self._e11_manifest()
        annotation={"source":"A","claim_key":"a-claim",
                    "quote":"The study proves absolutely everything.",
                    "stance":"support_candidate","note":"Owner note"}
        m["annotations"]=[annotation]
        with self.assertRaisesRegex(ValueError,"exactly once"):
            review_manifest(self.core,m)
        m["annotations"]=[]
        m["sources"]["A"]["owner_supplied"]=False
        with self.assertRaisesRegex(ValueError,"owner-supplied"):
            review_manifest(self.core,m)
        m=self._e11_manifest()
        m["sources"]["A"]["title"]="A forged title"
        with self.assertRaisesRegex(ValueError,"provenance mismatch"):
            review_manifest(self.core,m)
        m=self._e11_manifest()
        m["sources"]["A"]["receipt_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"provenance mismatch"):
            review_manifest(self.core,m)
        m=self._e11_manifest()
        m["source_snapshot_sha256"]="f"*64
        with self.assertRaisesRegex(ValueError,"stale"):
            review_manifest(self.core,m)
        m=self._e11_manifest()
        m["sources"]["A"]["event_id"]=99999
        with self.assertRaises(ValueError):
            review_manifest(self.core,m)

    def test_e11_rejects_duplicate_quote_offsets_and_bogus_stance(self):
        m=self._e11_manifest()
        m["sources"]["A"]["text"] += " Associations were reported."
        m["annotations"]=[{"source":"A","claim_key":"a-claim",
                           "quote":"Associations were reported.",
                           "stance":"context","note":"User note"}]
        with self.assertRaisesRegex(ValueError,"exactly once"):
            review_manifest(self.core,m)
        m=self._e11_manifest()
        m["annotations"]=[{"source":"A","claim_key":"a-claim",
                           "quote":"Associations were reported.",
                           "stance":"scientifically_proven","note":"User note"}]
        with self.assertRaisesRegex(ValueError,"stance"):
            review_manifest(self.core,m)
        m=self._e11_manifest()
        m["annotations"]=[{"source":"A","claim_key":"a-claim",
                           "quote":"Associations were reported.",
                           "stance":"context","note":"User note"}]*2
        with self.assertRaisesRegex(ValueError,"duplicate annotation"):
            review_manifest(self.core,m)

    def test_e11_owner_text_files_are_filled_only_after_explicit_validation(self):
        template=self._e11_manifest()
        first=template["sources"]["A"]["text"]
        second=template["sources"]["B"]["text"]
        for source in template["sources"].values():
            source["text"]=""
            source["owner_supplied"]=False
            source["usage_rights_note"]=""
        original=self.core.read_bytes()
        ready=fill_template(self.core,template,first.encode(),second.encode(),
            rights_note_a="User-provided excerpt A for private study",
            rights_note_b="User-provided excerpt B for private study")
        self.assertFalse(template["sources"]["A"]["owner_supplied"])
        self.assertEqual(ready["sources"]["A"]["text"],first)
        self.assertEqual(ready["sources"]["B"]["text"],second)
        self.assertEqual(review_manifest(self.core,ready)["annotation_count"],0)
        self.assertEqual(original,self.core.read_bytes())
        with self.assertRaisesRegex(ValueError,"UTF-8"):
            fill_template(self.core,template,b"\xff"*40,second.encode(),
                rights_note_a="user supplied",rights_note_b="user supplied")
        with self.assertRaisesRegex(ValueError,"rights notes"):
            fill_template(self.core,template,first.encode(),second.encode(),
                rights_note_a="",rights_note_b="user supplied")

    def test_e11_cli_fill_requires_explicit_owner_permission(self):
        pair=review_all(self.core,question="genetiikka")["dossiers"][0]
        template=prepare(self.core,pair["source_a"]["event_id"],
                              pair["source_b"]["event_id"])
        input_path=self.root/"e11-owner-template.json"
        input_path.write_text(json.dumps(template))
        a=self.root/"owner-a.txt"
        b=self.root/"owner-b.txt"
        a.write_text("Methods: Measure genetic associations and network expressions.")
        b.write_text("Results: A network method was compared with existing markers.")
        outfile=self.root/"e11-owner-filled.json"
        base=["--klone-db",str(self.core),"--fill",str(input_path),
              "--source-a-file",str(a),"--source-b-file",str(b),
              "--rights-note-a","Owner-supplied private excerpt A",
              "--rights-note-b","Owner-supplied private excerpt B",
              "--output",str(outfile)]
        with self.assertRaises(SystemExit):
            evidence_main(base)
        self.assertFalse(outfile.exists())
        self.assertEqual(evidence_main(base+["--owner-confirms-supplied-text"]),0)
        result=json.loads(outfile.read_text())
        self.assertTrue(result["sources"]["A"]["owner_supplied"])
        self.assertTrue(result["sources"]["B"]["owner_supplied"])
        self.assertEqual(result["sources"]["A"]["text"],a.read_text())
        self.assertEqual(self.core_before,self.core.read_bytes())

    def test_e11_cli_names_missing_local_input_instead_of_unhelpful_missing(self):
        import contextlib
        import io
        pair=review_all(self.core,question="genetiikka")["dossiers"][0]
        ids=(pair["source_a"]["event_id"],pair["source_b"]["event_id"])
        manifest=prepare(self.core,*ids)
        template=self.root/"e11-template-exists.json"
        template.write_text(json.dumps(manifest))
        a=self.root/"missing-a.txt"
        b=self.root/"missing-b.txt"
        b.write_text("Allowed study excerpt is stored as plain text.")
        output=self.root/"not-created-e11.json"
        args=["--klone-db",str(self.core),"--fill",str(template),
              "--source-a-file",str(a),"--source-b-file",str(b),
              "--rights-note-a","User-supplied research text A",
              "--rights-note-b","User-supplied research text B",
              "--owner-confirms-supplied-text",
              "--output",str(output)]
        for target,expected in ((a,"Lahdeteksti A"),(b,"Lahdeteksti B")):
            if target==b:
                a.write_text("Allowed excerpt text is present in source A.")
                b.unlink()
            stderr=io.StringIO()
            with contextlib.redirect_stderr(stderr):
                with self.assertRaises(SystemExit):
                    evidence_main(args)
            self.assertIn(expected+": missing:",stderr.getvalue())
            self.assertIn(str(target),stderr.getvalue())
            self.assertFalse(output.exists())
        self.assertEqual(self.core_before,self.core.read_bytes())

    def test_e11_refuses_oversized_data_and_missing_explicit_consent(self):
        m=self._e11_manifest()
        m["sources"]["B"]["text"]="A"*60001
        with self.assertRaisesRegex(ValueError,"text must"):
            review_manifest(self.core,m)
        m=self._e11_manifest()
        m["sources"]["B"]["usage_rights_note"]=""
        with self.assertRaisesRegex(ValueError,"usage-rights note"):
            review_manifest(self.core,m)
        m=self._e11_manifest()
        m["annotations"]=[{}]*41
        with self.assertRaisesRegex(ValueError,"limit exceeded"):
            review_manifest(self.core,m)

    def test_e11_cli_prepares_owner_editable_template_without_database_writes(self):
        pair=review_all(self.core,question="genetiikka")["dossiers"][0]
        first=pair["source_a"]["event_id"]
        second=pair["source_b"]["event_id"]
        target=self.root/"e11-template.json"
        before=self.core.read_bytes()
        result=evidence_main([
            "--klone-db",str(self.core),"--question","genetiikka",
            "--prepare",str(first),str(second),"--output",str(target)])
        self.assertEqual(result,0)
        prepared=json.loads(target.read_text())
        self.assertFalse(prepared["sources"]["A"]["owner_supplied"])
        self.assertEqual(prepared["annotations"],[])
        self.assertTrue(prepared["sources"]["A"]["source_url"].startswith("https://"))
        self.assertTrue(prepared["sources"]["A"]["title"])
        self.assertIn(prepared["sources"]["A"]["source_class"],
                      ("research_preprint","indexed_research","news_or_reference_feed"))
        self.assertEqual(before,self.core.read_bytes())

    def test_e112_candidates_are_verbatim_and_reviewer_tasks_are_unperformed(self):
        manifest=self._e11_manifest()
        before=self.core.read_bytes()
        result=suggest(self.core,manifest,per_source_limit=3)
        self.assertEqual(result["kind"],"klone-e11-2-evidence-review-candidates")
        self.assertTrue(2<=result["candidate_count"]<=6)
        self.assertEqual(result["council_completed_reviews"],0)
        self.assertEqual(result["council_vote_count"],0)
        self.assertEqual(result["reviewer_assignment_state"],"proposed_not_performed")
        self.assertFalse(result["source_texts_embedded"])
        self.assertFalse(any(result["authority"].values()))
        self.assertEqual(result["annotation_count"],0)
        self.assertEqual(result,suggest(self.core,manifest,per_source_limit=3))
        ids={m["id"] for m in catalog()["members"]}
        for c in result["candidates"]:
            source=manifest["sources"][c["source"]]["text"]
            self.assertEqual(
                source[c["char_start"]:c["char_end"]],c["quote"])
            self.assertEqual(source.count(c["quote"]),1)
            self.assertIn(c["proposed_reviewer"]["member_id"],ids)
            self.assertEqual(c["proposed_reviewer"]["state"],
                             "pending_not_executed")
            self.assertEqual(c["suggested_stance"],"context")
            self.assertTrue(c["quote_matched_owner_text"])
            self.assertFalse(c["quote_authenticated_against_publisher"])
            self.assertFalse(c["scientific_truth_verified"])
            self.assertFalse(c["review_completed"])
        self.assertEqual(self.core.read_bytes(),before)
        self.assertEqual(manifest["annotations"],[])

    def test_e112_summary_is_not_automatically_authentic_primary_evidence(self):
        manifest=self._e11_manifest()
        manifest["sources"]["A"]["usage_rights_note"] = (
            "Omistajan toimittama lähdeselostus, ei varmennettu kokoteksti")
        manifest["sources"]["B"]["usage_rights_note"] = (
            "AI-generated summary, not an authenticated paper")
        report=suggest(self.core,manifest)
        self.assertEqual(report["source_info"]["A"]["content_origin"],
                         "owner_declared_summary_unverified")
        self.assertEqual(report["source_info"]["B"]["content_origin"],
                         "owner_declared_summary_unverified")
        for role in ("A","B"):
            self.assertFalse(report["source_info"][role][
                "publisher_full_text_authenticated"])
        self.assertTrue(all(not x["scientific_truth_verified"]
                            for x in report["candidates"]))

    def test_e112_rejects_fake_provenance_missing_consent_and_unsafe_limits(self):
        manifest=self._e11_manifest()
        for limit in (0,13,True):
            with self.assertRaises(ValueError):
                suggest(self.core,manifest,per_source_limit=limit)
        manifest["source_snapshot_sha256"]="x"*64
        with self.assertRaisesRegex(ValueError,"stale"):
            suggest(self.core,manifest)
        manifest=self._e11_manifest()
        manifest["sources"]["B"]["owner_supplied"]=False
        with self.assertRaisesRegex(ValueError,"owner-supplied"):
            suggest(self.core,manifest)
        manifest=self._e11_manifest()
        manifest["sources"]["A"]["receipt_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"provenance mismatch"):
            suggest(self.core,manifest)

    def test_e112_skips_ambiguous_duplicate_phrases_in_local_text(self):
        manifest=self._e11_manifest()
        repeated="Methods: This method is only a demonstration."
        manifest["sources"]["A"]["text"]=(
            repeated+" "+repeated+" Unique result: A genetic experiment is described."
        )
        report=suggest(self.core,manifest,per_source_limit=8)
        self.assertTrue(report["candidates"])
        self.assertFalse(any(repeated==c["quote"] for c in report["candidates"]))
        self.assertEqual(
            [c["source"] for c in report["candidates"] if c["source"]=="A"],
            sorted(c["source"] for c in report["candidates"] if c["source"]=="A"))

    def test_e112_cli_generates_only_new_offline_proposal_report(self):
        manifest=self._e11_manifest()
        owner=self.root/"e112-manifest.json"
        outfile=self.root/"e112-suggestions.json"
        owner.write_text(json.dumps(manifest))
        before=self.core.read_bytes()
        result=candidate_main([
            "--klone-db",str(self.core),"--manifest",str(owner),
            "--per-source-limit","4","--output",str(outfile),
        ])
        self.assertEqual(result,0)
        parsed=json.loads(outfile.read_text())
        self.assertEqual(parsed["schema_version"],1)
        self.assertGreaterEqual(parsed["candidate_count"],2)
        self.assertFalse(parsed["authority"]["memory_write"])
        self.assertTrue(all(c["source_text_sha256"] for c in parsed["candidates"]))
        self.assertEqual(before,self.core.read_bytes())
        with self.assertRaises(SystemExit):
            candidate_main([
                "--klone-db",str(self.core),"--manifest",str(owner),
                "--output",str(outfile),
            ])
        self.assertEqual(before,self.core.read_bytes())

    def test_e113_explicit_selection_creates_only_owner_context_annotations(self):
        manifest=self._e11_manifest()
        proposals=suggest(self.core,manifest,per_source_limit=4)
        ids=[c["candidate_id"] for c in proposals["candidates"][:3]]
        before=self.core.read_bytes()
        with self.assertRaisesRegex(ValueError,"owner must explicitly"):
            accept_context(self.core,manifest,proposals,ids)
        selected=accept_context(
            self.core,manifest,proposals,ids,
            owner_confirms_selection=True)
        self.assertEqual(selected["annotations"][0]["stance"],"context")
        self.assertEqual([a["stance"] for a in selected["annotations"]],
                         ["context"]*len(ids))
        self.assertEqual(selected["e11_context_selection"]["selected_candidate_ids"],ids)
        self.assertFalse(selected["e11_context_selection"]["scientific_truth_verified"])
        self.assertFalse(selected["e11_context_selection"]["council_review_completed"])
        self.assertEqual(manifest["annotations"],[])
        report=review_manifest(self.core,selected)
        self.assertEqual(report["annotation_count"],len(ids))
        self.assertEqual(report["epistemic_state"],"owner_annotated_not_verified")
        self.assertEqual(report["opposing_annotation_candidates"],[])
        self.assertEqual(report["council_state"]["completed_reviews"],0)
        self.assertFalse(any(report["authority"].values()))
        self.assertEqual(before,self.core.read_bytes())

    def test_e113_tampered_proposals_forged_quote_and_stale_origin_denied(self):
        from copy import deepcopy
        manifest=self._e11_manifest()
        proposals=suggest(self.core,manifest)
        ids=[proposals["candidates"][0]["candidate_id"]]
        changed=deepcopy(proposals)
        changed["candidates"][0]["quote"]="Unverified fabricated evidence"
        with self.assertRaisesRegex(ValueError,"stale or altered"):
            accept_context(self.core,manifest,changed,ids,
                           owner_confirms_selection=True)
        changed=deepcopy(proposals)
        changed["candidates"][0]["proposed_reviewer"]["member_id"]=1234567
        with self.assertRaisesRegex(ValueError,"stale or altered"):
            accept_context(self.core,manifest,changed,ids,
                           owner_confirms_selection=True)
        changed=deepcopy(manifest)
        changed["sources"]["A"]["text"]+=" Extra sentence was added."
        with self.assertRaisesRegex(ValueError,"stale or altered"):
            accept_context(self.core,changed,proposals,ids,
                           owner_confirms_selection=True)
        with self.assertRaisesRegex(ValueError,"unknown candidate"):
            accept_context(self.core,manifest,proposals,["deadbeef"],
                           owner_confirms_selection=True)
        with self.assertRaisesRegex(ValueError,"distinct"):
            accept_context(self.core,manifest,proposals,ids*2,
                           owner_confirms_selection=True)
        with self.assertRaisesRegex(ValueError,"distinct"):
            accept_context(self.core,manifest,proposals,[],
                           owner_confirms_selection=True)
        changed=deepcopy(manifest)
        changed["annotations"]=[{"not":"empty"}]
        with self.assertRaisesRegex(ValueError,"unannotated"):
            accept_context(self.core,changed,proposals,ids,
                           owner_confirms_selection=True)

    def test_e113_cli_no_consent_no_write_and_successful_review_chain(self):
        manifest=self._e11_manifest()
        proposal=suggest(self.core,manifest)
        root=self.root
        source=root/"e11-3-input.json"
        candidates=root/"e11-3-proposals.json"
        selected=root/"e11-3-selected.json"
        checked=root/"e11-3-reviewed.json"
        source.write_text(json.dumps(manifest))
        candidates.write_text(json.dumps(proposal))
        base=["--klone-db",str(self.core),"--manifest",str(source),
              "--proposals",str(candidates),"--all-context",
              "--output",str(selected)]
        before=self.core.read_bytes()
        with self.assertRaises(SystemExit):
            accept_main(base)
        self.assertFalse(selected.exists())
        self.assertEqual(accept_main(base+[
            "--owner-confirms-candidate-selection"]),0)
        approved=json.loads(selected.read_text())
        self.assertEqual(len(approved["annotations"]),proposal["candidate_count"])
        self.assertEqual(evidence_main([
            "--klone-db",str(self.core),"--review",str(selected),
            "--output",str(checked)]),0)
        report=json.loads(checked.read_text())
        self.assertEqual(report["annotation_count"],proposal["candidate_count"])
        self.assertFalse(report["authority"]["scientific_truth_verified"])
        self.assertEqual(report["council_state"]["recorded_votes"],0)
        self.assertEqual(self.core.read_bytes(),before)

    def _e114_reviewed(self):
        manifest=self._e11_manifest()
        # These are artificial test texts. They must never become verified papers.
        title=manifest["sources"]["A"]["title"]
        manifest["sources"]["A"]["text"]=(
            title+".\n"
            "Methods: Sample gene markers were compared across groups.\n"
            "Tekijöiden mukaan tarkkuus parani vertailussa.\n"
            "Automaattinen arviointi ei todista tutkimustulosta.\n"
            "Mitä epävarmuutta mittauksiin liittyy?\n"
        )
        proposals=suggest(self.core,manifest,per_source_limit=12)
        ids=[c["candidate_id"] for c in proposals["candidates"]]
        selected=accept_context(self.core,manifest,proposals,ids,
                                owner_confirms_selection=True)
        ledger=review_manifest(self.core,selected)
        return manifest,proposals,selected,ledger

    def test_e114_classifies_real_owner_local_context_and_not_source_truth(self):
        original=self.core.read_bytes()
        _,proposals,selected,ledger=self._e114_reviewed()
        quality=audit_quality(self.core,selected,ledger)
        self.assertEqual(quality["kind"],"klone-e11-4-context-quality-audit")
        self.assertEqual(quality["context_quote_count"],len(proposals["candidates"]))
        self.assertEqual(quality["scientifically_verified_quote_count"],0)
        self.assertEqual(quality["independent_council_reviews"],0)
        self.assertFalse(quality["memory_write"])
        self.assertFalse(quality["primary_publication_authenticated"])
        self.assertFalse(quality["scientific_truth_verified"])
        counts=quality["counts_by_kind"]
        self.assertGreaterEqual(counts["publication_title_not_evidence"],1)
        self.assertGreaterEqual(counts["open_question_not_evidence"],1)
        self.assertGreaterEqual(counts["editorial_caution_not_evidence"],1)
        self.assertGreaterEqual(counts["attributed_research_claim_needs_primary_check"],1)
        self.assertEqual(quality,audit_quality(self.core,selected,ledger))
        for item in quality["source_quality_flags"]:
            source=selected["sources"][item["source"]]["text"]
            self.assertEqual(source[item["char_start"]:item["char_end"]],
                             item["quote"])
            self.assertFalse(item["valid_scientific_evidence"])
            self.assertFalse(item["exact_match_in_original_publication"])
            self.assertFalse(item["reviewer_completed"])
        self.assertEqual(original,self.core.read_bytes())

    def test_e114_summary_quality_flag_is_not_publisher_authentication(self):
        _,proposals,selected,ledger=self._e114_reviewed()
        selected["sources"]["A"]["usage_rights_note"]=(
            "Omistajan toimittama lähdeselostus, ei varmennettu kokoteksti")
        selected["sources"]["B"]["usage_rights_note"]=(
            "AI-generated summary, source text not independently authenticated")
        current=review_manifest(self.core,selected)
        quality=audit_quality(self.core,selected,current)
        self.assertTrue(quality["source_quality_flags"])
        for row in quality["source_quality_flags"]:
            self.assertEqual(row["content_origin"],"owner_declared_summary_unverified")
            self.assertFalse(row["valid_scientific_evidence"])

    def test_e114_rejects_tampered_ledger_attestation_and_non_context_stance(self):
        from copy import deepcopy
        _,proposals,selected,ledger=self._e114_reviewed()
        changed=deepcopy(ledger)
        changed["quote_anchors"][0]["quote"]="FORGED QUOTE"
        with self.assertRaisesRegex(ValueError,"does not match"):
            audit_quality(self.core,selected,changed)
        changed=deepcopy(selected)
        changed["e11_context_selection"]["selection_explicitly_authorized"]=False
        with self.assertRaisesRegex(ValueError,"selection attestation"):
            audit_quality(self.core,changed,ledger)
        changed=deepcopy(selected)
        changed["annotations"][0]["stance"]="support_candidate"
        with self.assertRaisesRegex(ValueError,"context only"):
            audit_quality(self.core,changed,ledger)
        changed=deepcopy(selected)
        changed["sources"]["B"]["receipt_sha256"]="0"*64
        with self.assertRaisesRegex(ValueError,"provenance mismatch"):
            audit_quality(self.core,changed,ledger)
        changed=deepcopy(selected)
        changed["e11_context_selection"]["selected_candidate_ids"]=[]
        with self.assertRaisesRegex(ValueError,"identity/count"):
            audit_quality(self.core,changed,ledger)

    def test_e114_cli_creates_private_report_only_once_and_preserves_memory(self):
        _,proposals,selected,ledger=self._e114_reviewed()
        manifest_file=self.root/"e114-context.json"
        ledger_file=self.root/"e114-ledger.json"
        outfile=self.root/"e114-quality.json"
        manifest_file.write_text(json.dumps(selected))
        ledger_file.write_text(json.dumps(ledger))
        before=self.core.read_bytes()
        args=["--klone-db",str(self.core),"--selected",str(manifest_file),
              "--ledger",str(ledger_file),"--output",str(outfile)]
        self.assertEqual(quality_main(args),0)
        data=json.loads(outfile.read_text())
        self.assertGreater(data["context_quote_count"],0)
        self.assertEqual(data["e11_3_ledger_sha256"],ledger["report_sha256"])
        self.assertEqual(data["scientifically_verified_quote_count"],0)
        with self.assertRaises(SystemExit):
            quality_main(args)
        self.assertEqual(before,self.core.read_bytes())

    def test_e10_readonly_council_workbench_endpoints(self):
        import os
        from klone.api import get_repository
        from klone.main import create_app
        from klone.limbo_main_research_canary import app as canary
        pair=review_all(self.core,question="genetiikka")["dossiers"][0]
        ids={"q":"genetiikka","first_event_id":pair["source_a"]["event_id"],
             "second_event_id":pair["source_b"]["event_id"]}
        app=create_app()
        app.dependency_overrides[get_repository]=lambda:KloneRepository(self.core)
        before=self.core.read_bytes()
        with TestClient(app) as client:
            r=client.get("/api/limbo-atlas/council-workbench",params=ids)
            self.assertEqual(r.status_code,200,r.text[:500])
            self.assertEqual(r.json()["seat_count"],72)
            self.assertEqual(client.post("/api/limbo-atlas/council-workbench",
                                         json=ids).status_code,405)
        with patch.dict(os.environ,{"KLONE_MAIN_RESEARCH_DB":str(self.core)}):
            with TestClient(canary) as client:
                self.assertEqual(client.get("/health").json()["feature_version"],"E10")
                self.assertEqual(client.get("/api/limbo-atlas/council-workbench",
                                            params=ids).status_code,200)
        self.assertEqual(before,self.core.read_bytes())

    def test_e9_get_only_apis_reject_writes_and_fake_papers(self):
        import os
        from klone.api import get_repository
        from klone.main import create_app
        from klone.limbo_main_research_canary import app as canary
        app=create_app()
        app.dependency_overrides[get_repository]=lambda:KloneRepository(self.core)
        pair=radar(self.core,"genetiikka")["cross_discipline_candidates"][0]
        params={"q":"genetiikka","first_event_id":pair["first_event_id"],
                "second_event_id":pair["second_event_id"]}
        before=self.core.read_bytes()
        with TestClient(app) as client:
            response=client.get("/api/limbo-atlas/dossier",params=params)
            self.assertEqual(response.status_code,200,response.text[:500])
            self.assertEqual(response.json()["kind"],"klone-atlas-e9-pair-dossier")
            self.assertEqual(client.get("/api/limbo-atlas/dossier",params={
                **params,"first_event_id":999999}).status_code,422)
            self.assertEqual(client.post("/api/limbo-atlas/dossier",
                                         json=params).status_code,405)
        with patch.dict(os.environ,{"KLONE_MAIN_RESEARCH_DB":str(self.core)}):
            with TestClient(canary) as client:
                self.assertEqual(client.get("/health").json()["feature_version"],"E10")
                self.assertEqual(client.get("/api/limbo-atlas/dossier",
                                            params=params).status_code,200)
                self.assertEqual(client.get("/api/limbo-atlas/dossiers",
                                            params={"q":"genetiikka"}).status_code,200)
                self.assertEqual(client.post("/api/limbo-atlas/dossier",
                                             json=params).status_code,405)
        self.assertEqual(before,self.core.read_bytes())

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
        self.assertIn("/api/limbo-atlas/dossier?q=",js.text)
        self.assertIn("hiddenDuplicatePairs",js.text)
        self.assertIn("E9.1",js.text)
        self.assertIn("Avaa E9-lähdeparin tutkimuskortti",js.text)
        self.assertIn("Avaa E10 · kaikki 72 neuvoston tehtävää",js.text)
        self.assertIn("/api/limbo-atlas/council-workbench?q=",js.text)
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
        self.assertIn("klone.limbo_source_dossiers",launcher)
        self.assertIn("klone.limbo_council_workbench",launcher)
        self.assertIn("klone.limbo_doctor",launcher)
        self.assertNotIn("first_event_id=26",launcher)
        self.assertIn("/api/limbo-atlas/dossiers?q=",launcher)

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
