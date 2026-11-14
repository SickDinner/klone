from pathlib import Path
import tempfile
from types import SimpleNamespace
from sqlite3 import OperationalError
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from klone.council72_memory import public_memory_observation
from klone.council72_session import demo_session, run_session
from klone.cognition_memory import MemoryProbe
from klone.hypervisor_dispatch import DispatchDenied
from klone.main import create_app
from klone.repository import KloneRepository


class CouncilMemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repository = KloneRepository(Path(self.tmp.name)/'memory.sqlite')
        self.repository.initialize()

    def tearDown(self):
        self.tmp.cleanup()

    def test_real_public_counts_and_persistent_audit_without_memory_writes(self):
        result = public_memory_observation(self.repository, limit=5)
        self.assertEqual(result['sample']['event_count'], 0)
        self.assertFalse(result['raw_memory_included'])
        self.assertFalse(result['provenance_authenticated'])
        self.assertEqual(result['observation']['courier_id'], 30)
        self.assertEqual(result['observation']['stance'], 'unknown')
        self.assertEqual(self.repository.list_memory_events(room_id='public-room',limit=10,offset=0), [])
        events = self.repository.list_audit_events(room_id='public-room',limit=10)
        self.assertEqual({r['event_type'] for r in events}, {'council72_memory_delegated','council72_memory_completed'})
        self.assertTrue(all(result['audit_trace_id'] in row['metadata_json'] for row in events))

    def test_corrected_count_sample_is_preserved_but_not_treated_as_success(self):
        probe = MemoryProbe('public-room', 5, 2, 1, 3, 5, True)
        with patch('klone.council72_memory.probe_memory', return_value=probe):
            result = public_memory_observation(self.repository, limit=5)
        self.assertEqual(result['sample']['corrected_event_count'], 3)
        self.assertTrue(result['sample']['truncated'])
        request = demo_session()
        request['steps'] = [{'observations':[result['observation']]}]
        session = run_session(request)
        self.assertEqual(session['rounds'][0]['review_status'], 'insufficient_sources')
        self.assertEqual(session['rounds'][0]['rings'][2]['supporting_source_groups'], 0)

    def test_failed_audit_prevents_actual_memory_read(self):
        with (patch.object(self.repository,'record_audit_event',side_effect=OSError('audit unavailable')),
              patch('klone.council72_memory.probe_memory') as probe):
            with self.assertRaises(OSError): public_memory_observation(self.repository)
            probe.assert_not_called()

    def test_failed_completion_audit_prevents_result_release(self):
        original = self.repository.record_audit_event
        def audit(**kwargs):
            if kwargs['event_type'] == 'council72_memory_completed': raise OSError('completion unavailable')
            return original(**kwargs)
        with patch.object(self.repository,'record_audit_event',side_effect=audit):
            with self.assertRaises(OSError): public_memory_observation(self.repository)
        self.assertEqual({r['event_type'] for r in self.repository.list_audit_events(room_id='public-room')},
                         {'council72_memory_delegated','council72_memory_failed'})

    def test_output_guard_denial_prevents_memory_read(self):
        with (patch('klone.council72_memory.output_guard.evaluate',return_value=SimpleNamespace(decision='blocked')),
              patch('klone.council72_memory.probe_memory') as probe):
            with self.assertRaises(DispatchDenied): public_memory_observation(self.repository)
            probe.assert_not_called()
        self.assertEqual(self.repository.list_audit_events(room_id='public-room')[0]['event_type'], 'council72_memory_denied')

    def test_limit_rejected_before_any_audit_or_read(self):
        for value in (True,0,201,'5'):
            with self.subTest(value=value), self.assertRaises(ValueError): public_memory_observation(self.repository,limit=value)
        self.assertEqual(self.repository.list_audit_events(room_id='public-room'), [])

    def test_api_fixed_public_scope_and_invalid_privilege_parameters(self):
        app = create_app()
        app.state.repository = self.repository
        client = TestClient(app)
        result = client.post('/api/cognition/council72/memory-observation',json={'limit':5})
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.json()['sample']['room_id'],'public-room')
        for body in ({'room_id':'sealed-room'},{'actor_role':'owner'},{'limit':True},{'limit':201}):
            self.assertEqual(client.post('/api/cognition/council72/memory-observation',json=body).status_code,422)

    def test_api_audit_unavailable_returns_503(self):
        app = create_app()
        app.state.repository = self.repository
        for error in (OSError('audit down'), OperationalError('database is locked')):
            with self.subTest(error=error), patch.object(self.repository,'record_audit_event',side_effect=error):
                response = TestClient(app).post('/api/cognition/council72/memory-observation',json={'limit':5})
                self.assertEqual(response.status_code,503)


if __name__ == '__main__': unittest.main()
