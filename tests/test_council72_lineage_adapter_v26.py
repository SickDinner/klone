"""Council72 lineage adapter tests; safe even when source claim is synthetic."""
import json
import unittest
from unittest.mock import patch
from klone.council72_lineage_adapter_v26 import (
    _nodes_from_normalized_observations, project_replayable_council_session)
from klone.evidence_lineage_v26 import analyze_lineage


def obs(i, **kwargs):
    r={'id':f'id{i}', 'claim_key':'test-claim', 'source_group':f'source{i}',
       'source_ref':f'dataset:{i}', 'stance':'supports', 'classification':'public',
       'supersedes':None}
    r.update(kwargs)
    return r


def digests(*refs):
    return {f'dataset:{i}':f'{i:064x}' for i in refs}


class CouncilLineageAdapterV26UnitTests(unittest.TestCase):
    def test_two_declared_sources_conservatively_projected(self):
        nodes=_nodes_from_normalized_observations([obs(1),obs(2)],digest_by_source_ref=digests(1,2))
        report=analyze_lineage(nodes)
        self.assertEqual(report['claims'][0]['review_status'],'candidate_for_manual_review')
        self.assertFalse(report['source_independence_authenticated'])

    def test_same_digest_merges_even_with_new_ref(self):
        m=digests(1,2)
        m['dataset:2']=m['dataset:1']
        nodes=_nodes_from_normalized_observations([obs(1),obs(2)],digest_by_source_ref=m)
        self.assertEqual(analyze_lineage(nodes)['claims'][0]['supporting_clusters'],1)

    def test_no_synthetic_hash_of_reference_as_fallback(self):
        with self.assertRaisesRegex(ValueError,'source_digest_missing'):
            _nodes_from_normalized_observations([obs(1)],digest_by_source_ref={})

    def test_extra_digest_reference_denied(self):
        with self.assertRaisesRegex(ValueError,'unexpected_source_digest_reference'):
            _nodes_from_normalized_observations([obs(1)],digest_by_source_ref=digests(1,2))

    def test_uppercase_digest_denied(self):
        with self.assertRaisesRegex(ValueError,'invalid_supplied_source_digests'):
            _nodes_from_normalized_observations([obs(1)],digest_by_source_ref={'dataset:1':'A'*64})

    def test_sealed_classification_correctly_mapped(self):
        nodes=_nodes_from_normalized_observations([obs(1,classification='sealed')],
                                                    digest_by_source_ref=digests(1))
        self.assertEqual((nodes[0].room_id,nodes[0].classification),('sealed-room','intimate'))

    def test_restricted_classification_correctly_mapped(self):
        nodes=_nodes_from_normalized_observations([obs(1,classification='restricted')],
                                                    digest_by_source_ref=digests(1))
        self.assertEqual((nodes[0].room_id,nodes[0].classification),('restricted-room','personal'))

    def test_cross_classification_same_source_quarantined(self):
        rows=[obs(1),obs(2,source_group='source1',classification='sealed')]
        result=analyze_lineage(_nodes_from_normalized_observations(rows,digest_by_source_ref=digests(1,2)))
        self.assertEqual(result['claims'][0]['review_status'],'quarantined_cross_room_lineage')

    def test_cross_zone_correction_fails_closed(self):
        rows=[obs(1),obs(2,supersedes='id1',classification='sealed')]
        with self.assertRaisesRegex(ValueError,'cross_scope_supersession_denied'):
            analyze_lineage(_nodes_from_normalized_observations(rows,digest_by_source_ref=digests(1,2)))

    def test_same_zone_supersession_preserves_history(self):
        rows=[obs(1),obs(2,supersedes='id1')]
        report=analyze_lineage(_nodes_from_normalized_observations(rows,digest_by_source_ref=digests(1,2)))
        self.assertEqual(report['claims'][0]['superseded_evidence_count'],1)

    def test_unknown_council_class_denied(self):
        with self.assertRaises(ValueError):
            _nodes_from_normalized_observations([obs(1,classification='root')],digest_by_source_ref=digests(1))

    def test_invalid_domain_denied(self):
        with self.assertRaisesRegex(ValueError,'invalid_projection_domain'):
            _nodes_from_normalized_observations([obs(1)],digest_by_source_ref=digests(1),domain='root')

    def test_unexpected_observation_shape_denied(self):
        with self.assertRaisesRegex(ValueError,'invalid_normalized_observation'):
            _nodes_from_normalized_observations([{'id':'id1'}],digest_by_source_ref=digests(1))

    def test_output_graph_never_contains_raw_ref(self):
        nodes=_nodes_from_normalized_observations([obs(1),obs(2)],digest_by_source_ref=digests(1,2))
        blob=json.dumps(analyze_lineage(nodes))
        self.assertNotIn('dataset:',blob)

    def test_not_an_approval_api(self):
        import klone.council72_lineage_adapter_v26 as m
        for method in ('approve','execute','publish','write_memory','send'):
            self.assertFalse(hasattr(m,method))


try:
    from klone.council72_session import demo_session, run_session, session_replays
except ImportError:
    demo_session=run_session=session_replays=None


@unittest.skipIf(run_session is None,"full Council72 imports required for integration tests")
class CouncilLineageAdapterV26IntegrationTests(unittest.TestCase):
    def test_real_replayable_demo_projection_is_simulation_only(self):
        report=run_session(demo_session())
        sources={o['source_ref'] for step in report['request']['steps']
                 for o in step['observations']}
        mapping={src:f'{i+1:064x}' for i,src in enumerate(sorted(sources))}
        out=project_replayable_council_session(report,digest_by_source_ref=mapping)
        self.assertTrue(out['session_report_replays'])
        self.assertEqual(out['review_status'],'simulation_only')
        self.assertFalse(out['eligible_for_real_world_use'])
        self.assertFalse(out['approval_granted'])
        self.assertFalse(out['memory_write_enabled'])
        self.assertEqual(out['observation_count'],report['observation_count'])
        self.assertNotIn('synthetic:ring',json.dumps(out))

    def test_mutated_replay_report_denied(self):
        report=run_session(demo_session())
        report['trace_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'unreplayable_council_session'):
            project_replayable_council_session(report,digest_by_source_ref={})

    def test_real_demo_with_missing_attested_map_fails_closed(self):
        report=run_session(demo_session())
        with self.assertRaisesRegex(ValueError,'source_digest_missing'):
            project_replayable_council_session(report,digest_by_source_ref={})


if __name__=='__main__':unittest.main()
