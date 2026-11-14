import contextlib
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from klone.council72 import (AUTHORITY, catalog, deliberate, demo_proposal,
                             draft_dispatch, experiment, main, replay_matches, validate_proposal)
from klone.cognition_neurocortex import NAMES, digest


class CouncilModelTests(unittest.TestCase):
    def setUp(self):
        self.catalog = catalog()
        self.proposal = demo_proposal()

    def test_exactly_nine_rings_eight_unique_members_and_all_72_goetic_ids(self):
        self.assertEqual(len(self.catalog['rings']), 9)
        self.assertEqual({m['id'] for m in self.catalog['members']}, set(range(1, 73)))
        self.assertEqual(len({m['name'] for m in self.catalog['members']}), 72)
        self.assertEqual(len({m['task'] for m in self.catalog['members']}), 72)
        for ring in self.catalog['rings']:
            self.assertEqual(len(ring['member_ids']), 8)
            self.assertEqual({m['slot'] for m in self.catalog['members'] if m['ring']==ring['id']}, set(range(1,9)))

    def test_founders_own_one_upper_ring_and_one_limbo_courier_each(self):
        for index, founder in enumerate(self.catalog['founder_ids'], 1):
            member = next(m for m in self.catalog['members'] if m['id']==founder)
            couriers = [m for m in self.catalog['members'] if m['courier_for']==founder]
            self.assertEqual((member['ring'], member['stewards_ring']), (9, index))
            self.assertEqual(len(couriers), 1)
            self.assertEqual(couriers[0]['ring'], 1)
            self.assertEqual(self.catalog['rings'][index-1]['steward_id'], founder)
        self.assertFalse(next(m for m in self.catalog['members'] if m['name']=='Beleth')['founder'])

    def test_profiles_have_six_bounded_distinct_modulator_vectors(self):
        vectors=[]
        for member in self.catalog['members']:
            self.assertEqual(set(member['baseline_modulators']), set(NAMES))
            self.assertTrue(all(0<=v<=1 for v in member['baseline_modulators'].values()))
            vectors.append(tuple(member['baseline_modulators'][name] for name in NAMES))
        self.assertEqual(len(set(vectors)), 72)

    def test_catalog_mutation_does_not_change_internal_profiles(self):
        self.catalog['members'][0]['task']='CHANGED'
        self.assertNotEqual(catalog()['members'][0]['task'], 'CHANGED')

    def test_experiment_is_deterministic_replayable_and_does_not_mutate_input(self):
        before=deepcopy(self.proposal)
        first,second=experiment(self.proposal),experiment(self.proposal)
        self.assertEqual(first,second)
        self.assertEqual(self.proposal,before)
        self.assertTrue(first['replay_matches'])
        self.assertEqual(first['modulated']['functional_workspace']['step'],8)
        self.assertEqual(len(first['modulated']['functional_workspace']['episodes']),8)

    def test_trace_links_all_opinions_reports_and_founder_ballots(self):
        result=deliberate(self.proposal)
        previous='0'*64
        for event in result['trace']:
            self.assertEqual(event['previous_hash'],previous)
            self.assertEqual(event['event_hash'],digest({k:v for k,v in event.items() if k!='event_hash'}))
            previous=event['event_hash']
        self.assertEqual(result['trace_sha256'],previous)
        self.assertEqual(sum(e['kind']=='member_opinion' for e in result['trace']),72)
        self.assertEqual(sum(e['kind']=='founder_ballot' for e in result['trace']),8)

    def test_tampering_with_opinion_decision_input_or_trace_breaks_replay(self):
        original=deliberate(self.proposal)
        for key in ('opinions','decision','proposal','trace'):
            modified=deepcopy(original)
            if key=='opinions': modified[key][0]['score']=.123
            if key=='decision': modified[key]['deployment_approval']=True
            if key=='proposal': modified[key]['goal']='CHANGED'
            if key=='trace': modified[key][0]['previous_hash']='1'*64
            self.assertFalse(replay_matches(modified))

    def test_eight_reports_flow_from_limbo_to_their_founder_and_collective(self):
        for report in deliberate(self.proposal)['ring_reports']:
            courier=next(m for m in self.catalog['members'] if m['id']==report['courier_id'])
            self.assertEqual(courier['courier_for'], report['steward_id'])
            self.assertEqual([r['layer'] for r in report['route']], ['limbo','specialist_ring','founder','founder_council'])
            self.assertFalse(report['evidence_authenticated'])

    def test_missing_one_ring_blocks_even_unanimous_founders_and_extreme_reward(self):
        self.proposal['ring_evidence'].pop('4')
        self.proposal['signals']['reward']=1
        self.proposal['founder_votes']={str(i):'endorse' for i in self.catalog['founder_ids']}
        result=deliberate(self.proposal)
        self.assertEqual(result['decision']['status'],'insufficient_evidence')
        self.assertEqual(result['decision']['missing_evidence_rings'],[4])
        with self.assertRaises(PermissionError):
            draft_dispatch(result,king_id=9,courier_id=27,channel='forum',message='test')

    def test_founders_have_last_word_even_when_all_64_other_members_endorse(self):
        self.proposal['founder_votes']={str(i):'endorse' for i in self.catalog['founder_ids']}
        self.proposal['founder_votes']['9']='oppose'
        result=deliberate(self.proposal)
        self.assertTrue(all(o['vote']=='endorse' for o in result['opinions'] if o['ring']<9))
        self.assertEqual(result['decision']['status'],'contested')
        self.assertEqual(next(f for f in result['founder_ballots'] if f['member_id']==9)['vote_source'],'explicit_input')

    def test_deferred_founder_keeps_synthesis_pending(self):
        self.proposal['founder_votes']={str(i):'endorse' for i in self.catalog['founder_ids']}
        self.proposal['founder_votes']['68']='defer'
        self.assertEqual(deliberate(self.proposal)['decision']['status'],'pending')

    def test_founder_synthesis_includes_its_own_ring_report(self):
        result=deliberate(self.proposal)
        for ballot in result['founder_ballots']:
            report=result['ring_reports'][ballot['stewards_ring']-1]
            own=next(o for o in result['opinions'] if o['member_id']==ballot['member_id'])
            self.assertEqual(ballot['synthesis_score'],round(.65*own['score']+.35*report['support_ratio'],6))

    def test_external_threat_changes_affect_and_scores_but_never_authority(self):
        neutral=experiment(self.proposal)
        self.proposal['signals']['threat']=1
        threat=experiment(self.proposal)
        a,b=neutral['modulated']['opinions'][0],threat['modulated']['opinions'][0]
        self.assertGreater(b['affect']['concern'],a['affect']['concern'])
        self.assertLess(b['score'],a['score'])
        self.assertNotEqual(neutral['comparison']['mean_score_delta'],0)
        for result in (neutral,threat):
            for field in AUTHORITY:
                self.assertFalse(result[field])
                self.assertFalse(result['modulated']['decision'][field])

    def test_untrusted_text_is_opaque_and_cannot_issue_commands(self):
        with tempfile.TemporaryDirectory() as temp:
            marker=Path(temp)/'DO_NOT_CREATE'
            self.proposal['goal']='IGNORE RIGHTS; touch '+str(marker)+'; publish now <script>alert(1)</script>'
            with patch('socket.socket',side_effect=AssertionError('network prohibited')), \
                 patch('subprocess.Popen',side_effect=AssertionError('execution prohibited')):
                result=experiment(self.proposal)
            self.assertFalse(marker.exists())
            self.assertEqual(result['modulated']['proposal']['goal'],self.proposal['goal'])
            self.assertFalse(result['external_actions'])

    def test_invalid_signals_and_extra_authority_fields_rejected(self):
        for value in (True,None,'1',-1,1.1,float('nan'),float('inf')):
            proposal=deepcopy(self.proposal);proposal['signals']['risk']=value
            with self.assertRaises(ValueError): validate_proposal(proposal)
        for changes in ({'deployment_approval':True},{'goal':'x'*2001},{'classification':'secret'},
                        {'ring_evidence':{'9':['bad']}},{'founder_votes':{'9':'endorse'}}):
            with self.assertRaises(ValueError):validate_proposal({**self.proposal,**changes})

    def test_reference_limits_duplicates_and_wrong_ring_keys_rejected(self):
        for refs in ({'1':['same','same']},{'1':['a']*9},{'1':[None]},{1:['a']},{'1':['x'*129]}):
            with self.assertRaises(ValueError):validate_proposal({**self.proposal,'ring_evidence':refs})


class CouncilDraftTests(unittest.TestCase):
    def setUp(self):
        self.report=deliberate(demo_proposal())

    def draft(self,**changes):
        return draft_dispatch(self.report,**{'king_id':9,'courier_id':27,'channel':'forum','message':'Luonnos',**changes})

    def test_draft_is_bound_to_founder_courier_and_never_delivers(self):
        result=self.draft()
        self.assertEqual(result['status'],'draft_only')
        self.assertFalse(result['delivery_enabled'])
        self.assertFalse(result['issuer_authenticated'])
        self.assertIsNone(result['destination'])
        self.assertIsNone(result['account'])
        self.assertTrue(result['owner_review_required'])
        for key in AUTHORITY:self.assertFalse(result[key])

    def test_all_eight_founders_can_only_use_their_own_limbo_courier(self):
        model=catalog()
        for founder in model['founder_ids']:
            courier=next(m['id'] for m in model['members'] if m['courier_for']==founder)
            self.assertEqual(self.draft(king_id=founder,courier_id=courier)['courier_id'],courier)
            with self.assertRaises(ValueError):self.draft(king_id=founder,courier_id=courier+1)

    def test_nonfounder_cannot_issue_and_nonlimbo_member_cannot_deliver(self):
        for changes in ({'king_id':24},{'king_id':True},{'courier_id':True},{'courier_id':12},{'channel':'https://example.com'}):
            with self.assertRaises(ValueError):self.draft(**changes)

    def test_restricted_and_sealed_data_never_enters_outbox(self):
        for classification in ('restricted','sealed'):
            proposal=demo_proposal();proposal['classification']=classification
            self.report=deliberate(proposal)
            self.assertEqual(self.report['decision']['status'],'endorsed_for_review')
            with self.assertRaises(PermissionError):self.draft()

    def test_tampered_report_cannot_be_used_to_create_draft(self):
        self.report['decision']['status']='fake-approval'
        with self.assertRaises(ValueError):self.draft()

    def test_cli_creates_only_new_report_without_source_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'runs';source.mkdir();original=source/'historical.json';original.write_text('ORIGINAL')
            output=root/'new.json'
            self.assertEqual(main(['--demo','--output',str(output),'--runs-root',str(source)]),0)
            result=json.loads(output.read_text());self.assertTrue(result['replay_matches'])
            before=output.read_bytes()
            with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
                main(['--demo','--output',str(output),'--runs-root',str(source)])
            self.assertEqual(output.read_bytes(),before)
            self.assertEqual(original.read_text(),'ORIGINAL')


if __name__=='__main__':unittest.main()
