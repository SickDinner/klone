"""Bounded 9x8 portfolio planning without external tool execution."""
import json
import unittest
from klone.council72_portfolio_v26 import ReviewCandidate, plan_council72_review
from klone.evidence_lineage_v26 import EvidenceLineageNode


def evidence(i, claim='claim1', **kwargs):
    data=dict(node_id=f'n{i}',claim_key=claim,domain='cognition',
              source_group=f'source{i}',content_sha256=f'{i:064x}',
              stance='supports',room_id='public-room',classification='public')
    data.update(kwargs)
    return EvidenceLineageNode(**data)


def task(i,ring=1,seat=1,**kwargs):
    d=dict(task_id=f'task{i}',claim_key='claim1',domain='cognition',
           ring=ring,seat=seat,priority=80,estimated_tokens=100)
    d.update(kwargs)
    return ReviewCandidate(**d)


class Council72PortfolioV26Tests(unittest.TestCase):
    def setUp(self):
        self.sources=[evidence(1),evidence(2)]

    def test_manual_queue_only(self):
        report=plan_council72_review(self.sources,[task(1)])
        self.assertEqual(report['queued_task_count'],1)
        self.assertFalse(report['tasks_executed'])
        self.assertFalse(report['approval_granted'])
        self.assertFalse(report['actual_hypervisor_authorization_performed'])

    def test_contested_candidate_deferred(self):
        report=plan_council72_review(self.sources+[evidence(3,stance='contradicts')],[task(1)])
        self.assertEqual(report['queued_task_count'],0)
        self.assertEqual(report['tasks'][0]['queue_result'],'evidence_not_ready_for_review')

    def test_collect_evidence_deferred_claim_is_queueable_for_human(self):
        report=plan_council72_review(self.sources+[evidence(3,stance='unknown')],
                                     [task(1,purpose='request_more_evidence')])
        self.assertEqual(report['queued_task_count'],1)
        self.assertFalse(report['tasks_executed'])

    def test_cross_room_evidence_never_automatic_review_candidate(self):
        rows=self.sources+[evidence(3,room_id='sealed-room',classification='intimate',
                                   dependencies=('n1',))]
        report=plan_council72_review(rows,[task(1)])
        self.assertEqual(report['queued_task_count'],0)

    def test_global_budget_enforced(self):
        report=plan_council72_review(self.sources,[task(1,ring=1),task(2,ring=2)],
                                     max_total_tokens=100)
        self.assertEqual(report['queued_task_count'],1)
        self.assertEqual(report['planned_tokens'],100)

    def test_per_ring_budget_enforced(self):
        report=plan_council72_review(self.sources,[task(1,ring=1,seat=1),task(2,ring=1,seat=2)],
                                     max_ring_tokens=100)
        self.assertEqual(report['queued_task_count'],1)
        self.assertEqual(report['planned_tokens_per_ring']['1'],100)

    def test_ring_round_robin_does_not_let_ring1_hog(self):
        tasks=[task(1,ring=1,seat=1,estimated_tokens=100),
               task(2,ring=1,seat=2,estimated_tokens=100),
               task(3,ring=2,seat=1,estimated_tokens=100)]
        report=plan_council72_review(self.sources,tasks,max_total_tokens=200)
        self.assertEqual([x['task_id'] for x in report['tasks']],['task1','task3','task2'])
        self.assertEqual(report['queued_task_count'],2)

    def test_priority_within_ring(self):
        report=plan_council72_review(self.sources,[task(1,ring=1,seat=1,priority=1),
                                                   task(2,ring=1,seat=2,priority=99)])
        self.assertEqual(report['tasks'][0]['task_id'],'task2')

    def test_72_seat_bounded(self):
        tasks=[task(i,ring=(i-1)//8+1,seat=(i-1)%8+1,estimated_tokens=1)
               for i in range(1,73)]
        report=plan_council72_review(self.sources,tasks)
        self.assertEqual(report['total_task_count'],72)
        self.assertEqual(report['queued_task_count'],72)
        self.assertEqual(len(report['planned_tokens_per_ring']),9)
        self.assertEqual(sum(report['planned_tokens_per_ring'].values()),72)

    def test_over_72_denied(self):
        with self.assertRaises(ValueError):
            plan_council72_review(self.sources,[task(i,ring=1,seat=i) for i in range(1,74)])

    def test_duplicate_seat_denied(self):
        with self.assertRaisesRegex(ValueError,'duplicate_task_or_seat'):
            plan_council72_review(self.sources,[task(1),task(2)])

    def test_duplicate_task_denied(self):
        with self.assertRaisesRegex(ValueError,'duplicate_task_or_seat'):
            plan_council72_review(self.sources,[task(1),task(1,ring=2)])

    def test_unknown_claim_denied(self):
        with self.assertRaisesRegex(ValueError,'unknown_council_claim'):
            plan_council72_review(self.sources,[task(1,claim_key='missing')])

    def test_bool_resource_budget_denied(self):
        with self.assertRaisesRegex(ValueError,'invalid_budget'):
            plan_council72_review(self.sources,[task(1)],max_total_tokens=True)

    def test_invalid_role_of_this_planner(self):
        for name in ('authorize','run','execute','approve','deploy'):
            import klone.council72_portfolio_v26 as m
            self.assertFalse(hasattr(m,name))

    def test_invalid_ring_denied(self):
        with self.assertRaises(ValueError):
            task(1,ring=10)

    def test_invalid_seat_denied(self):
        with self.assertRaises(ValueError):
            task(1,seat=9)

    def test_invalid_purpose_denied(self):
        with self.assertRaises(ValueError):
            task(1,purpose='publish')

    def test_invalid_estimate_denied(self):
        with self.assertRaises(ValueError):
            task(1,estimated_tokens=-1)

    def test_invalid_numeric_bool_denied(self):
        with self.assertRaises(ValueError):
            task(1,priority=True)

    def test_ignores_input_order_for_same_config(self):
        candidates=[task(1,ring=1),task(2,ring=2)]
        self.assertEqual(plan_council72_review(self.sources,candidates),
                         plan_council72_review(list(reversed(self.sources)),list(reversed(candidates))))

    def test_no_raw_content_leaked(self):
        output=json.dumps(plan_council72_review(self.sources,[task(1)]))
        self.assertNotIn('source1',output)
        self.assertNotIn('content_sha256',output)


if __name__=='__main__':
    unittest.main()
