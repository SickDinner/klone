"""Reproducible, bounded red-team tests for v2.7 withdrawal simulations."""
import json
import unittest
from klone.evidence_lineage_v26 import EvidenceLineageNode
from klone.evidence_counterfactual_v27 import simulate_source_withdrawals


def e(i, *, group=None, claim='claim1', stance='supports', dependencies=(), supersedes=None, **changes):
    values=dict(node_id=f'n{i}',claim_key=claim,domain='research',source_group=group or f'g{i}',
                content_sha256=f'{i:064x}',stance=stance,room_id='public-room',
                classification='public',dependencies=dependencies,supersedes=supersedes)
    values.update(changes)
    return EvidenceLineageNode(**values)


class CounterfactualV27Tests(unittest.TestCase):
    def test_two_independent_declared_groups_are_fragile(self):
        result=simulate_source_withdrawals([e(1),e(2)])
        self.assertTrue(result['coverage_complete'])
        self.assertEqual(len(result['cases']),2)
        self.assertTrue(all(x['candidate_status_downgraded'] for x in result['cases']))
        self.assertEqual(result['claims'][0]['tested_group_removals_downgrading_candidate'],2)

    def test_three_sources_survive_one_group(self):
        result=simulate_source_withdrawals([e(1),e(2),e(3)])
        self.assertTrue(all(not x['status_changes'] for x in result['cases']))
        self.assertEqual(result['claims'][0]['tested_group_removals_downgrading_candidate'],0)

    def test_dependency_cascade_removes_derived_source_even_if_named_differently(self):
        items=[e(1,group='root'),e(2,group='child',dependencies=('n1',)),e(3,group='independent')]
        result=simulate_source_withdrawals(items)
        root=next(x for x in result['cases'] if x['removed_observation_count']==2)
        self.assertTrue(root['candidate_status_downgraded'])
        self.assertEqual(root['status_changes'][0]['to'],'insufficient_distinct_lineages')

    def test_supersession_descendant_cascade_does_not_resurrect_old_evidence(self):
        items=[e(1,group='old'),e(2,group='corrected',supersedes='n1'),e(3,group='independent')]
        result=simulate_source_withdrawals(items)
        self.assertTrue(any(x['removed_observation_count']==2 for x in result['cases']))
        self.assertEqual(sum(x['candidate_status_downgraded'] for x in result['cases']),3)

    def test_withdrawal_of_only_source_means_no_evidence(self):
        r=simulate_source_withdrawals([e(1)])
        self.assertEqual(r['cases'][0]['status_changes'][0]['to'],'no_evidence_remaining')
        self.assertFalse(r['claims'][0]['single_declared_group_failure_detected'])

    def test_duplicate_digest_claims_not_pretended_independent(self):
        a=e(1)
        b=e(2,content_sha256=a.content_sha256)
        r=simulate_source_withdrawals([a,b])
        self.assertEqual(r['claims'][0]['baseline_status'],'insufficient_distinct_lineages')

    def test_cross_room_quarantine_stays_an_explicit_original_status(self):
        r=simulate_source_withdrawals([e(1),e(2,dependencies=('n1',),
                                   room_id='sealed-room',classification='intimate')])
        self.assertEqual(r['claims'][0]['baseline_status'],'quarantined_cross_room_lineage')
        self.assertFalse(r['approval_granted'])

    def test_contested_input_not_autorized_by_simulated_removal(self):
        r=simulate_source_withdrawals([e(1),e(2),e(3,stance='contradicts')])
        self.assertEqual(r['claims'][0]['baseline_status'],'contested_requires_review')
        self.assertFalse(r['execution_enabled'])

    def test_multiple_claims_and_missing_claim_after_removal(self):
        r=simulate_source_withdrawals([e(1,claim='a'),e(2,claim='b'),e(3,claim='b')])
        self.assertTrue(any(change['claim_key']=='a' and change['to']=='no_evidence_remaining'
                 for c in r['cases'] for change in c['status_changes']))

    def test_order_invariant_and_report_fingerprint(self):
        items=[e(1),e(2),e(3)]
        self.assertEqual(simulate_source_withdrawals(items), simulate_source_withdrawals(items[::-1]))

    def test_permutation_of_dependencies(self):
        a=[e(1),e(2),e(3,dependencies=('n1','n2'))]
        b=[e(3,dependencies=('n2','n1')),e(2),e(1)]
        self.assertEqual(simulate_source_withdrawals(a),simulate_source_withdrawals(b))

    def test_coverage_limit_not_misrepresented_as_full(self):
        r=simulate_source_withdrawals([e(i) for i in range(1,7)],max_source_groups=2)
        self.assertEqual(r['withdrawals_examined'],2)
        self.assertFalse(r['coverage_complete'])
        self.assertTrue(all(not x['complete_one_group_withdrawal_coverage'] for x in r['claims']))

    def test_bounded_invalid_limits(self):
        for value in [0,True,33,1.5,'3',None]:
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'invalid_withdrawal_limit'):
                simulate_source_withdrawals([e(1)],max_source_groups=value)

    def test_rejects_cycles_and_missing_provenance_edges(self):
        with self.assertRaisesRegex(ValueError,'missing_evidence_dependency'):
            simulate_source_withdrawals([e(1,dependencies=('missing',))])
        with self.assertRaisesRegex(ValueError,'cyclic_evidence_lineage'):
            simulate_source_withdrawals([e(1,dependencies=('n2',)),e(2,dependencies=('n1',))])

    def test_no_source_labels_or_raw_hash_in_json(self):
        r=simulate_source_withdrawals([e(1,group='sensitive_root'),e(2,group='other')])
        blob=json.dumps(r)
        self.assertNotIn('sensitive_root',blob)
        self.assertNotIn('content_sha256',blob)
        self.assertNotIn(f'{1:064x}',blob)

    def test_no_external_action_or_new_authority(self):
        from klone import evidence_counterfactual_v27 as module
        for x in ('publish','approve','execute','dispatch','write_memory','load_key'):
            self.assertFalse(hasattr(module,x))
        report=simulate_source_withdrawals([e(1),e(2)])
        self.assertFalse(report['memory_write_enabled'])
        self.assertFalse(report['approval_granted'])
        self.assertFalse(report['source_independence_authenticated'])

    def test_invalid_inputs_fail_closed(self):
        for nodes in [[],[4],'hello',None]:
            with self.subTest(nodes=nodes), self.assertRaises(ValueError):
                simulate_source_withdrawals(nodes)

if __name__=='__main__':
    unittest.main()
