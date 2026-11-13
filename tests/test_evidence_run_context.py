import copy
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from klone.evidence_forensics import generate
from klone.evidence_log_analysis import analyze
from klone.evidence_status import inspect as inspect_status
from klone.evidence_observatory import compare_history
from klone.evidence_network import validate_run, build_packet
from klone.evidence_run_context import context_id, digest, suite_snapshot, syntax_check, validate_context
from forensics_fixture import create_run, save_packet
from run_context_fixture import environment, upgrade

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('battery_context_tests', ROOT / 'tools/termux_evidence_battery.py')
battery = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(battery)
sys.path.insert(0, str(ROOT / 'tools'))
PIPELINE_SPEC = importlib.util.spec_from_file_location('pipeline_context_tests', ROOT / 'tools/termux_evidence_pipeline.py')
pipeline = importlib.util.module_from_spec(PIPELINE_SPEC)
PIPELINE_SPEC.loader.exec_module(pipeline)


class EvidenceRunContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.runs = self.root / 'runs'
        self.runs.mkdir()

    def v2(self, name='a', status='passed', minute=1):
        run = create_run(self.runs, name, status=status, minute=minute)
        data = upgrade(json.loads((run / 'run.json').read_text()))
        self.save(run, data)
        return run, data

    def save(self, run, data):
        (run / 'run.json').write_text(json.dumps(data))
        save_packet(run)

    def test_v1_packet_remains_byte_identical_and_v2_reads_without_rewriting(self):
        v1 = create_run(self.runs, 'old')
        original = (v1 / 'evidence-packet.json').read_bytes()
        self.v2('new')
        before = {str(p):(p.read_bytes(),p.stat().st_mtime_ns) for p in self.runs.rglob('*') if p.is_file()}
        report = generate(self.runs)
        self.assertEqual({r['manifest_schema_version'] for r in report['runs']}, {1,2})
        self.assertTrue(all(r['packet']['matches_source'] for r in report['runs']))
        self.assertEqual(before, {str(p):(p.read_bytes(),p.stat().st_mtime_ns) for p in self.runs.rglob('*') if p.is_file()})
        self.assertEqual(original, (v1 / 'evidence-packet.json').read_bytes())

    def test_matching_v2_profiles_confirm_local_passed_failed(self):
        self.v2('a')
        self.v2('b', 'failed', 2)
        c = generate(self.runs)['comparisons'][0]
        self.assertEqual(c['regressed_stages'], ['full'])
        self.assertTrue(c['execution_contexts_match'])
        self.assertFalse(c['origin_authenticated'])

    def test_changed_command_or_suite_or_environment_stays_unknown(self):
        self.v2('a')
        run, baseline = self.v2('b', 'failed', 2)
        for changed in ('command','suite','environment','collector'):
            with self.subTest(changed=changed):
                data = copy.deepcopy(baseline)
                c = data['execution']
                if changed == 'command':
                    c['commands']['full'].append('--changed-option')
                elif changed == 'suite':
                    c['test_suite_before']['sha256'] = 'e' * 64
                    c['test_suite_after']['sha256'] = 'e' * 64
                elif changed == 'collector':
                    c['collector_sha256'] = c['collector_after_sha256'] = 'e' * 64
                else:
                    data['environment']['packages']['pytest'] = '9.3.0'
                    c['environment_after_sha256'] = digest(data['environment'])
                c['comparison_id'] = context_id(data['environment'], c)
                self.save(run, data)
                comparison = generate(self.runs)['comparisons'][0]
                self.assertFalse(comparison['comparable'])
                self.assertEqual(comparison['regressed_stages'], [])
                self.assertIn('full', comparison['unknown_transitions'])

    def test_v1_v2_are_not_promoted_to_equal_context(self):
        old = create_run(self.runs, 'a')
        self.v2('b', 'failed', 2)
        data = json.loads((old / 'run.json').read_text())
        data['environment'] = environment()
        self.save(old, data)
        c = generate(self.runs)['comparisons'][0]
        self.assertFalse(c['comparable'])
        self.assertEqual(c['context_comparison_scope'], 'unavailable')

    def test_context_changes_during_run_block_ci_dossier(self):
        run, data = self.v2()
        data['execution']['test_suite_after']['sha256'] = 'e' * 64
        data['execution']['context_consistent'] = False
        data['overall'] = 'failed'
        self.save(run, data)
        ci = {'a'*40:{'commit':'a'*40,'workflow':'KLONE regression guard','conclusion':'success'}}
        r = generate(self.runs, ci_by_commit=ci)['runs'][0]
        self.assertTrue(r['trust']['manifest_reports_required_stages_passed'])
        self.assertFalse(r['trust']['execution_context_consistent'])
        self.assertFalse(r['github_comparison']['consistent_claims'])
        self.assertEqual(r['decision_dossier']['decision'], 'blocked')

    def test_incomplete_capture_blocks_success_even_with_zero_exit_codes(self):
        run, data = self.v2()
        data['stages']['full']['capture_complete'] = False
        data['collection_complete'] = False
        data['overall'] = 'failed'
        self.save(run, data)
        r = generate(self.runs)['runs'][0]
        self.assertFalse(r['trust']['collection_complete'])
        self.assertFalse(r['decision_input_status']['required_stages_passed'])

    def test_malformed_context_and_forged_digest_rejected(self):
        _, baseline = self.v2()
        for change in ('missing','digest','argv','boolean','collection','context_consistency'):
            with self.subTest(change=change):
                data = copy.deepcopy(baseline)
                c = data['execution']
                if change == 'missing':
                    del data['execution']
                elif change == 'digest':
                    c['comparison_id'] = '0' * 64
                elif change == 'argv':
                    c['commands']['full'] = 'python -m pytest; arbitrary-command'
                elif change == 'boolean':
                    c['context_version'] = True
                elif change == 'collection':
                    data['collection_complete'] = False
                else:
                    c['context_consistent'] = False
                with self.assertRaises((ValueError,KeyError,TypeError)):
                    validate_run(data)

    def test_profile_normalizes_checkout_and_interpreter_paths_only(self):
        _, data = self.v2()
        other = upgrade(copy.deepcopy(data), cwd='/different-checkout', python='/other-venv/bin/python')
        self.assertEqual(data['execution']['comparison_id'], other['execution']['comparison_id'])

    def test_android_and_windows_path_claims_validate_on_the_analysis_host(self):
        _, data = self.v2()
        validate_context(data)
        data['execution']['cwd'] = 'C:\\fixture\\checkout'
        data['execution']['environment_overrides']['PYTHONPATH'] = 'C:\\fixture\\checkout\\src'
        validate_context(data)

    def test_v2_pipeline_preserves_platform_and_context_without_android_relabel(self):
        run, data = self.v2()
        record, inserted, _ = pipeline.import_report(run, self.root / 'ledger.sqlite')
        self.assertTrue(inserted)
        self.assertEqual(record['environment'], 'synthetic-test-unverified')
        self.assertEqual(record['details']['comparison_id'], data['execution']['comparison_id'])
        self.assertFalse(record['details']['device_identity_verified'])
        (run / 'torch_probe.log').unlink()
        with self.assertRaises(ValueError):
            pipeline.load_report(run)

    def test_v2_missing_or_wrong_typed_process_exit_code_rejected(self):
        _, data = self.v2()
        for value in (None,True,'0'):
            data['stages']['full']['exit_code'] = value
            with self.assertRaises(ValueError):
                validate_context(data)

    def test_status_and_observatory_do_not_bypass_v2_context_checks(self):
        a, _ = self.v2('a')
        b, data = self.v2('b', 'failed', 2)
        def statuses():
            return [{**inspect_status(p,p/'evidence-packet.json'),'run_name':p.name} for p in (a,b)]
        self.assertEqual(compare_history(statuses())[0]['regressed_stages'], ['full'])
        data['execution']['commands']['full'].append('--changed-profile')
        data['execution']['comparison_id'] = context_id(data['environment'],data['execution'])
        self.save(b,data)
        self.assertEqual(compare_history(statuses())[0]['regressed_stages'], [])
        data['execution']['context_consistent'] = False
        data['execution']['environment_after_sha256'] = 'f'*64
        self.save(b,data)
        self.assertEqual(inspect_status(b,b/'evidence-packet.json')['decision'], 'blocked')

    def test_suite_tracks_fixture_and_config_content_not_mtime_or_path(self):
        root = self.root / 'checkout'
        (root / 'tests').mkdir(parents=True)
        (root / 'tests/test_a.py').write_text('x=1')
        (root / 'tests/fixture.json').write_text('{}')
        (root / 'pyproject.toml').write_text('[project]')
        before = suite_snapshot(root)
        (root / 'tests/test_a.py').touch()
        self.assertEqual(before, suite_snapshot(root))
        (root / 'tests/fixture.json').write_text('{"changed":true}')
        self.assertNotEqual(before['sha256'], suite_snapshot(root)['sha256'])

    def test_suite_rejects_symlink_and_large_source(self):
        root = self.root / 'checkout'
        (root / 'tests').mkdir(parents=True)
        source = root / 'tests/test_a.py'
        source.write_text('x=1')
        with patch('klone.evidence_run_context.MAX_FILE_BYTES', 1):
            with self.assertRaises(ValueError):
                suite_snapshot(root)
        try:
            (root / 'tests/linked.py').symlink_to(source)
        except OSError:
            self.skipTest('symlinks unavailable')
        with self.assertRaises(ValueError):
            suite_snapshot(root)

    def test_syntax_does_not_execute_source_or_write_bytecode(self):
        source = self.root / 'source'
        source.mkdir()
        marker = self.root / 'EXECUTED'
        (source / 'a.py').write_text(f'open({str(marker)!r},"w").write("bad")')
        result = syntax_check(source)
        self.assertEqual(result['status'], 'passed')
        self.assertFalse(marker.exists())
        self.assertFalse((source / '__pycache__').exists())
        self.assertEqual(analyze(json.dumps(result).encode(), 'syntax')['reported_status'], 'passed')
        (source / 'b.py').write_text('def broken(:')
        failed = syntax_check(source)
        self.assertEqual(failed['status'], 'failed')
        self.assertEqual(analyze(json.dumps(failed).encode(), 'syntax')['reported_status'], 'failed')


class BatteryV2Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / 'checkout'
        (self.root / 'tests').mkdir(parents=True)
        (self.root / 'src/klone').mkdir(parents=True)
        (self.root / 'tools').mkdir()
        (self.root / 'tests/test_toy.py').write_text('x=1')
        (self.root / 'src/klone/evidence_run_context.py').write_text('x=1')
        (self.root / 'tools/termux_evidence_battery.py').write_text('x=1')
        self.output = self.base / 'new-run'
        self.python = Path(sys.executable)
        self.checkout = {'commit':'a'*40,'branch':'fixture','dirty':False}
        self.probe = {'environment':environment(),'executable':str(self.python),'prefix':'/fixture','virtualenv_reported':True}

    def collect(self, stage=None):
        def fake_stage(command,root,env,timeout):
            if stage:
                return stage(command,root,env,timeout)
            return {'exit_code':0,'status':'passed','capture_complete':True,'timed_out':False}, b'3 passed in 0.01s'
        with patch.object(battery,'checkout',return_value=self.checkout), \
             patch.object(battery,'probe_python',return_value=self.probe), \
             patch.object(battery,'run_stage',side_effect=fake_stage):
            return battery.run_battery(self.root,self.output,python=self.python)

    def test_new_run_creates_v2_and_original_packet_without_touching_sources(self):
        before = {str(p):(p.read_bytes(),p.stat().st_mtime_ns) for p in self.root.rglob('*') if p.is_file()}
        report = self.collect()
        self.assertEqual(report['schema_version'],2)
        self.assertEqual(report['overall'],'passed')
        self.assertEqual(before,{str(p):(p.read_bytes(),p.stat().st_mtime_ns) for p in self.root.rglob('*') if p.is_file()})
        self.assertEqual(json.loads((self.output/'evidence-packet.json').read_text()),build_packet(self.output))
        self.assertFalse(report['device_identity_verified'])
        validate_run(report)

    def test_existing_run_is_rejected_before_execution_and_never_overwritten(self):
        self.output.mkdir()
        artifact = self.output/'full.log'
        artifact.write_text('HISTORICAL')
        with patch.object(battery,'checkout',side_effect=AssertionError('no checkout or execution')):
            with self.assertRaises(ValueError):
                battery.run_battery(self.root,self.output,python=self.python)
        self.assertEqual(artifact.read_text(),'HISTORICAL')

    def test_output_inside_checkout_or_git_metadata_rejected(self):
        for output in (self.root/'new-run',self.base/'.git/new-run'):
            with self.subTest(output=output), self.assertRaises(ValueError):
                battery.run_battery(self.root,output,python=self.python)

    def test_symlink_output_parent_rejected(self):
        parent=self.base/'link'
        try:
            parent.symlink_to(self.root,target_is_directory=True)
        except OSError:
            self.skipTest('symlinks unavailable')
        with self.assertRaises(ValueError):
            battery.run_battery(self.root,parent/'new',python=self.python)

    def test_source_change_during_run_is_not_a_passing_context(self):
        def stage(*args):
            (self.root/'tests/test_toy.py').write_text('x=2')
            return {'exit_code':0,'status':'passed','capture_complete':True},b'3 passed in 0.01s'
        report=self.collect(stage)
        self.assertTrue(report['required_tests_passed'])
        self.assertFalse(report['execution']['context_consistent'])
        self.assertEqual(report['overall'],'failed')
        validate_run(report)

    def test_stage_stdout_and_stderr_are_combined_and_bounded(self):
        stage,raw=battery.run_stage([sys.executable,'-c','import sys; print("OUT",flush=True); print("ERR",file=sys.stderr,flush=True)'],self.root,dict(os.environ),10)
        self.assertTrue(stage['capture_complete'])
        self.assertEqual(raw.replace(b'\r\n', b'\n'),b'OUT\nERR\n')
        with patch.object(battery,'MAX_LOG',100):
            stage,raw=battery.run_stage([sys.executable,'-c','print("x"*500)'],self.root,dict(os.environ),10)
        self.assertFalse(stage['capture_complete'])
        self.assertEqual(stage['exit_code'],0)
        self.assertLessEqual(len(raw),100)

    def test_timeout_keeps_partial_output_but_never_complete_success(self):
        stage,raw=battery.run_stage([sys.executable,'-c','import time; print("PARTIAL",flush=True); time.sleep(3)'],self.root,dict(os.environ),1)
        self.assertTrue(stage['timed_out'])
        self.assertFalse(stage['capture_complete'])
        self.assertIn(b'PARTIAL',raw)
        self.assertEqual(stage['exit_code'],124)

    def test_probe_fails_closed_without_installing_dependencies(self):
        with patch.object(battery.subprocess,'run',return_value=subprocess.CompletedProcess([],1)) as run:
            with self.assertRaises(ValueError):
                battery.probe_python(self.python,self.root,{})
        self.assertFalse(run.call_args.kwargs['shell'])

    def test_probe_deduplicates_matching_editable_metadata_but_rejects_conflicts(self):
        distributions = [SimpleNamespace(metadata={'Name':'A_B'},version='1.0'),
                         SimpleNamespace(metadata={'Name':'a-b'},version='1.0')]
        output=io.StringIO()
        with patch('importlib.metadata.distributions',return_value=distributions), contextlib.redirect_stdout(output):
            exec(battery.PROBE,{})
        self.assertEqual(json.loads(output.getvalue())['environment']['packages'], {'a-b':'1.0'})
        distributions[1].version='2.0'
        with patch('importlib.metadata.distributions',return_value=distributions), self.assertRaises(ValueError):
            exec(battery.PROBE,{})

    def test_unknown_pytest_environment_options_rejected_before_execution(self):
        with patch.dict('os.environ',{'PYTEST_ADDOPTS':'-k secret-selection'}), \
             patch.object(battery,'checkout',side_effect=AssertionError('no test execution')):
            with self.assertRaises(ValueError):
                battery.run_battery(self.root,self.output,python=self.python)

    def test_cli_keeps_symlink_path_until_safety_validation(self):
        linked=self.base/'linked-output-parent'
        try:
            linked.symlink_to(self.root,target_is_directory=True)
        except OSError:
            self.skipTest('symlinks unavailable')
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            battery.main(['--root',str(self.root),'--python',str(self.python),'--output',str(linked/'new-run')])
        self.assertEqual(raised.exception.code,2)
        self.assertFalse((self.root/'new-run').exists())
