"""Adversarial, read-only lineage tests across KLONE's module domains."""
import json
import unittest
from dataclasses import replace
from klone.evidence_lineage_v26 import EvidenceLineageNode, analyze_lineage


def node(i, **kw):
    base=dict(node_id='n'+str(i),claim_key='claim1',domain='research',
              source_group='source'+str(i),content_sha256=f'{i:064x}',
              stance='supports',room_id='public-room',classification='public')
    base.update(kw)
    return EvidenceLineageNode(**base)


class EvidenceLineageV26Tests(unittest.TestCase):
    def test_two_distinct_declared_sources_only_candidate_for_review(self):
        r=analyze_lineage([node(1),node(2)])
        c=r['claims'][0]
        self.assertEqual(c['review_status'],'candidate_for_manual_review')
        self.assertFalse(r['execution_enabled'])
        self.assertFalse(r['approval_granted'])
        self.assertFalse(r['source_independence_authenticated'])
        self.assertTrue(c['single_cluster_withdrawal_changes_candidate'])

    def test_one_declared_source_never_quorum(self):
        r=analyze_lineage([node(1)])
        self.assertEqual(r['claims'][0]['review_status'],'insufficient_distinct_lineages')

    def test_same_content_different_source_names_collapses(self):
        r=analyze_lineage([node(1),node(2,content_sha256=f'{1:064x}')])
        self.assertEqual(r['claims'][0]['declared_source_group_count'],2)
        self.assertEqual(r['claims'][0]['supporting_clusters'],1)
        self.assertEqual(r['claims'][0]['review_status'],'insufficient_distinct_lineages')

    def test_same_group_different_hashes_collapses(self):
        r=analyze_lineage([node(1),node(2,source_group='source1')])
        self.assertEqual(r['claims'][0]['supporting_clusters'],1)

    def test_derived_evidence_does_not_add_second_vote(self):
        r=analyze_lineage([node(1),node(2,dependencies=('n1',))])
        self.assertEqual(r['claims'][0]['supporting_clusters'],1)
        self.assertEqual(r['input_edges'],1)

    def test_transitive_dependencies_collapse(self):
        r=analyze_lineage([node(1),node(2,dependencies=('n1',)),
                           node(3,dependencies=('n2',))])
        self.assertEqual(r['all_dependency_clusters'],1)

    def test_disagreeing_independent_source_requires_review(self):
        r=analyze_lineage([node(1),node(2),node(3,stance='contradicts')])
        self.assertEqual(r['claims'][0]['review_status'],'contested_requires_review')
        self.assertEqual(r['claims'][0]['contradicting_clusters'],1)

    def test_unknown_blocks_candidate(self):
        r=analyze_lineage([node(1),node(2),node(3,stance='unknown')])
        self.assertEqual(r['claims'][0]['review_status'],'unresolved_requires_review')

    def test_conflict_inside_same_root_detected(self):
        r=analyze_lineage([node(1),node(2,dependencies=('n1',),stance='contradicts')])
        self.assertEqual(r['claims'][0]['review_status'],'contested_requires_review')
        self.assertEqual(r['claims'][0]['supporting_clusters'],1)
        self.assertEqual(r['claims'][0]['contradicting_clusters'],1)

    def test_correction_does_not_double_count(self):
        r=analyze_lineage([node(1,stance='unknown'),node(2,supersedes='n1'),node(3)])
        c=r['claims'][0]
        self.assertEqual(c['active_evidence_count'],2)
        self.assertEqual(c['superseded_evidence_count'],1)
        self.assertEqual(c['review_status'],'candidate_for_manual_review')

    def test_correction_chain_only_latest_active(self):
        r=analyze_lineage([node(1),node(2,supersedes='n1'),
                           node(3,supersedes='n2'),node(4)])
        self.assertEqual(r['claims'][0]['superseded_evidence_count'],2)
        self.assertEqual(r['claims'][0]['active_evidence_count'],2)

    def test_superseded_all_unknown_results_non_candidate(self):
        r=analyze_lineage([node(1,stance='contradicts'),node(2,supersedes='n1',stance='unknown')])
        self.assertEqual(r['claims'][0]['review_status'],'unresolved_requires_review')

    def test_crossroom_dependency_quarantines(self):
        r=analyze_lineage([node(1),node(2,room_id='sealed-room',
            classification='intimate',dependencies=('n1',))])
        self.assertEqual(r['claims'][0]['review_status'],'quarantined_cross_room_lineage')
        self.assertFalse(r['cross_room_access_granted'])

    def test_crossroom_same_digest_quarantines_two_claims(self):
        r=analyze_lineage([node(1),node(2,room_id='sealed-room',
            classification='intimate',claim_key='claim2',content_sha256=f'{1:064x}')])
        self.assertTrue(all(x['review_status']=='quarantined_cross_room_lineage' for x in r['claims']))

    def test_different_rooms_without_link_remain_separate(self):
        r=analyze_lineage([node(1),node(2,room_id='sealed-room',
            classification='intimate',claim_key='claim2')])
        self.assertTrue(all(not x['cross_room_or_classification_lineage'] for x in r['claims']))

    def test_cross_scope_supersession_denied(self):
        with self.assertRaisesRegex(ValueError,'cross_scope_supersession'):
            analyze_lineage([node(1),node(2,claim_key='claim2',supersedes='n1')])

    def test_crossroom_supersession_denied(self):
        with self.assertRaisesRegex(ValueError,'cross_scope_supersession'):
            analyze_lineage([node(1),node(2,supersedes='n1',room_id='sealed-room',
                                classification='intimate')])

    def test_forked_correction_denied(self):
        with self.assertRaisesRegex(ValueError,'forked_supersession'):
            analyze_lineage([node(1),node(2,supersedes='n1'),node(3,supersedes='n1')])

    def test_missing_dependency_denied(self):
        with self.assertRaisesRegex(ValueError,'missing_evidence_dependency'):
            analyze_lineage([node(1,dependencies=('missing',))])

    def test_missing_supersession_denied(self):
        with self.assertRaisesRegex(ValueError,'missing_superseded_evidence'):
            analyze_lineage([node(1,supersedes='missing')])

    def test_dependency_cycle_denied(self):
        with self.assertRaisesRegex(ValueError,'cyclic_evidence_lineage'):
            analyze_lineage([node(1,dependencies=('n2',)),node(2,dependencies=('n1',))])

    def test_dependency_supersession_cycle_denied(self):
        with self.assertRaisesRegex(ValueError,'cyclic_evidence_lineage'):
            analyze_lineage([node(1,dependencies=('n2',)),node(2,supersedes='n1')])

    def test_duplicate_node_denied(self):
        with self.assertRaisesRegex(ValueError,'duplicate_evidence_id'):
            analyze_lineage([node(1),node(1)])

    def test_self_dependency_denied(self):
        with self.assertRaisesRegex(ValueError,'self_reference_denied'):
            node(1,dependencies=('n1',))

    def test_invalid_digest_denied(self):
        with self.assertRaises(ValueError):
            node(1,content_sha256='A'*64)

    def test_invalid_room_classification_denied(self):
        with self.assertRaises(ValueError):
            node(1,room_id='sandbox-room')

    def test_invalid_domain_denied(self):
        with self.assertRaises(ValueError):
            node(1,domain='council-godmode')

    def test_malicious_string_rejected(self):
        with self.assertRaises(ValueError):
            node(1,source_group='../../../private')

    def test_bool_parameter_denied(self):
        with self.assertRaises(ValueError):
            analyze_lineage([node(1)],minimum_candidate_clusters=True)

    def test_invalid_inputs_denied(self):
        for inputs in ([], 'str', [3], None):
            with self.subTest(inputs=inputs),self.assertRaises(ValueError):
                analyze_lineage(inputs)

    def test_permutation_invariance_and_digest(self):
        items=[node(1),node(2),node(3,dependencies=('n1',)),node(4,claim_key='claim2')]
        a=analyze_lineage(items)
        b=analyze_lineage(list(reversed(items)))
        self.assertEqual(a,b)

    def test_512_input_cap(self):
        items=[node(i,source_group='s'+str(i)) for i in range(1,514)]
        with self.assertRaisesRegex(ValueError,'invalid_evidence_set'):
            analyze_lineage(items)

    def test_many_different_claims_limit(self):
        with self.assertRaisesRegex(ValueError,'too_many_claims'):
            analyze_lineage([node(i,claim_key='claim'+str(i)) for i in range(1,130)])

    def test_all_12_domains_are_accepted_as_metadata(self):
        from klone.acceptance_matrix import DOMAINS
        items=[node(i+1,domain=domain,source_group='s'+str(i)) for i,domain in enumerate(DOMAINS)]
        r=analyze_lineage(items)
        self.assertEqual(r['claims'][0]['domain_count'],12)

    def test_no_raw_evidence_in_report(self):
        r=analyze_lineage([node(1),node(2)])
        encoded=json.dumps(r)
        self.assertNotIn('content_sha256',encoded)
        self.assertNotIn('source1',encoded)

    def test_declared_fingerprint_changes_for_different_evidence(self):
        a=analyze_lineage([node(1),node(2)])
        b=analyze_lineage([node(1),node(2,content_sha256=f'{5:064x}')])
        self.assertEqual(a['claims'],b['claims'])
        self.assertNotEqual(a['declared_input_sha256'],b['declared_input_sha256'])
        self.assertNotEqual(a['analysis_sha256'],b['analysis_sha256'])

    def test_order_of_parent_links_is_not_identity_change(self):
        items=[node(1),node(2),node(3,dependencies=('n1','n2'))]
        reordered=[node(3,dependencies=('n2','n1')),node(2),node(1)]
        self.assertEqual(analyze_lineage(items),analyze_lineage(reordered))

    def test_unhashable_dependency_denied_without_typeerror(self):
        with self.assertRaisesRegex(ValueError,'invalid_evidence_dependencies'):
            node(1,dependencies=(['n2'],))

    def test_unhashable_stance_denied_without_typeerror(self):
        with self.assertRaisesRegex(ValueError,'invalid_evidence_stance'):
            node(1,stance=['supports'])

    def test_no_execution_entrypoints(self):
        from klone import evidence_lineage_v26 as m
        for x in ('approve','execute','publish','write_memory','dispatch'):
            self.assertFalse(hasattr(m,x))

    def test_legacy_stance_claim_not_automatically_true(self):
        r=analyze_lineage([node(1),node(2)])
        self.assertFalse(r['source_digests_authenticated'])
        self.assertTrue(r['manual_review_required'])


if __name__ == '__main__':
    unittest.main()
