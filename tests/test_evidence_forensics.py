import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from klone.evidence_forensics import generate, main, render
from klone.evidence_log_analysis import analyze
from forensics_fixture import create_run, save_packet


class EvidenceForensicsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'runs'
        self.root.mkdir()

    def run_report(self, **kw):
        return generate(self.root, **kw)['runs'][0]

    def test_manifest_and_packet_present_are_separate_trust_dimensions(self):
        create_run(self.root)
        r = self.run_report()
        self.assertTrue(r['manifest']['structure_valid'])
        self.assertTrue(r['packet']['matches_source'])
        self.assertTrue(r['trust']['manifest_reports_required_stages_passed'])
        self.assertFalse(r['trust']['origin_authenticated'])
        self.assertFalse(r['trust']['test_execution_authenticated'])
        self.assertFalse(r['trust']['deployment_approval'])

    def test_manifest_missing(self):
        run = create_run(self.root)
        (run / 'run.json').unlink()
        r = self.run_report()
        self.assertEqual(r['manifest']['state'], 'missing')
        self.assertIsNone(r['trust']['manifest_structurally_valid'])
        self.assertEqual(r['quality']['category'], 'incomplete')

    def test_packet_missing_never_recreated(self):
        run = create_run(self.root, packet=False)
        r = self.run_report()
        self.assertEqual(r['packet']['state'], 'missing')
        self.assertEqual(r['recovery']['action'], 'inspect_source_artifacts')
        self.assertFalse((run / 'evidence-packet.json').exists())

    def test_manifest_and_packet_both_missing(self):
        (self.root / 'lost').mkdir()
        r = self.run_report()
        self.assertEqual(r['recovery']['action'], 'original_manifest_missing')
        self.assertIsNone(r['trust']['manifest_reports_required_stages_passed'])

    def test_stage_log_missing(self):
        run = create_run(self.root)
        (run / 'full.log').unlink()
        r = self.run_report()
        self.assertEqual(r['artifacts']['full.log']['state'], 'missing')
        self.assertEqual(r['stages']['full']['log_evidence']['reported_status'], 'unknown')
        self.assertIsNone(r['packet']['matches_source'])

    def test_empty_syntax_log_is_unknown_not_failed(self):
        create_run(self.root)
        r = self.run_report()
        stage = r['stages']['syntax']
        self.assertTrue(stage['log_evidence']['empty'])
        self.assertEqual(stage['log_evidence']['reported_status'], 'unknown')
        self.assertIsNone(stage['log_supports_claim'])
        self.assertIsNone(r['trust']['all_required_logs_support_claims'])
        self.assertEqual(r['contradictions'], [])

    def test_oversized_log_is_not_read_or_hashed(self):
        create_run(self.root)
        with patch('klone.evidence_artifact_inspector.MAX_LOG', 8):
            r = self.run_report()
        self.assertEqual(r['artifacts']['full.log']['state'], 'oversized')
        self.assertNotIn('sha256', r['artifacts']['full.log'])

    def test_invalid_json_manifest_is_isolated(self):
        run = create_run(self.root)
        (run / 'run.json').write_bytes(b'{broken')
        r = self.run_report()
        self.assertFalse(r['manifest']['structure_valid'])
        self.assertIn('manifest_invalid_json', r['errors'])

    def test_wrong_manifest_schema(self):
        run = create_run(self.root)
        manifest = json.loads((run / 'run.json').read_text())
        manifest['schema_version'] = 2
        (run / 'run.json').write_text(json.dumps(manifest))
        self.assertFalse(self.run_report()['manifest']['structure_valid'])

    def test_status_and_exit_code_contradiction(self):
        run = create_run(self.root)
        manifest = json.loads((run / 'run.json').read_text())
        manifest['stages']['full']['exit_code'] = 1
        (run / 'run.json').write_text(json.dumps(manifest))
        r = self.run_report()
        self.assertIn('full:exit_status_mismatch', r['contradictions'])
        self.assertEqual(r['quality']['category'], 'contradictory')

    def test_packet_sha_mismatch(self):
        run = create_run(self.root)
        data = json.loads((run / 'evidence-packet.json').read_text())
        data['packet_sha256'] = '0' * 64
        (run / 'evidence-packet.json').write_text(json.dumps(data))
        r = self.run_report()
        self.assertFalse(r['packet']['matches_source'])
        self.assertIn('packet_digest_mismatch', r['packet']['errors'])

    def test_changed_source_sha_is_detected(self):
        run = create_run(self.root)
        (run / 'local_deploy.log').write_text('4 passed in 0.2s')
        r = self.run_report()
        self.assertFalse(r['packet']['matches_source'])
        self.assertIn('packet_source_mismatch', r['packet']['errors'])

    def test_matching_packet_can_still_have_a_log_claim_contradiction(self):
        run = create_run(self.root)
        (run / 'full.log').write_text('1 failed in 0.1s')
        save_packet(run)
        r = self.run_report()
        self.assertTrue(r['packet']['matches_source'])
        self.assertIn('full:manifest_passed_log_failed', r['contradictions'])
        self.assertEqual(r['quality']['category'], 'contradictory')
        self.assertFalse(r['trust']['all_required_logs_support_claims'])

    def test_optional_absence_claim_is_separate_from_a_passing_test(self):
        run = create_run(self.root)
        r = self.run_report()
        self.assertEqual(r['stages']['torch_probe']['log_evidence']['reported_status'], 'not_present')
        self.assertTrue(r['stages']['torch_probe']['log_supports_claim'])
        (run / 'torch_probe.log').write_text('3 passed in 0.04s')
        save_packet(run)
        r = self.run_report()
        self.assertIn('torch_probe:manifest_not_present_log_passed', r['contradictions'])
        self.assertEqual(r['quality']['category'], 'contradictory')

    def test_symlink_run_rejected_without_following(self):
        run = create_run(self.root)
        (self.root / 'alias').symlink_to(run, target_is_directory=True)
        report = generate(self.root)
        self.assertEqual(len(report['runs']), 1)
        self.assertEqual(report['rejected_entries'], [{'name': 'alias', 'reason': 'symlink_rejected'}])

    def test_symlink_artifact_rejected(self):
        run = create_run(self.root)
        (run / 'full.log').unlink()
        (run / 'full.log').symlink_to(run / 'cognition.log')
        self.assertEqual(self.run_report()['artifacts']['full.log']['state'], 'symlink_rejected')

    def test_packet_path_traversal_is_never_followed(self):
        run = create_run(self.root)
        secret = Path(self.tmp.name) / 'secret'
        secret.write_text('NEVER_READ_THIS_SECRET')
        data = json.loads((run / 'evidence-packet.json').read_text())
        data['files']['../../secret'] = data['files'].pop('full.log')
        (run / 'evidence-packet.json').write_text(json.dumps(data))
        r = self.run_report()
        self.assertFalse(r['packet']['structure_valid'])
        self.assertNotIn('NEVER_READ_THIS_SECRET', json.dumps(r))
        self.assertEqual(secret.read_text(), 'NEVER_READ_THIS_SECRET')

    def test_passed_to_failed_confirmed_only_with_matching_content_and_context(self):
        create_run(self.root, 'a', minute=1)
        create_run(self.root, 'b', status='failed', minute=2)
        report = generate(self.root)
        self.assertEqual(report['confirmed_regression_transitions'], 1)
        self.assertEqual(report['comparisons'][0]['regressed_stages'], ['full'])
        self.assertFalse(report['comparisons'][0]['causality_established'])

    def test_passed_to_unknown_is_not_a_regression(self):
        create_run(self.root, 'a', minute=1)
        run = create_run(self.root, 'b', minute=2, packet=False)
        (run / 'run.json').unlink()
        report = generate(self.root)
        self.assertEqual(report['confirmed_regression_transitions'], 0)
        self.assertIn('full', report['comparisons'][0]['unknown_transitions'])

    def test_failed_to_passed_is_a_local_recovery(self):
        create_run(self.root, 'a', status='failed', minute=1)
        create_run(self.root, 'b', minute=2)
        c = generate(self.root)['comparisons'][0]
        self.assertEqual(c['regressed_stages'], [])
        self.assertEqual(c['recovered_stages'], ['full'])

    def test_incomplete_comparison_never_confirms_regression(self):
        create_run(self.root, 'a', minute=1, packet=False)
        create_run(self.root, 'b', status='failed', minute=2)
        c = generate(self.root)['comparisons'][0]
        self.assertFalse(c['comparable'])
        self.assertEqual(c['regressed_stages'], [])

    def test_unknown_environment_prevents_confirmed_regression(self):
        a = create_run(self.root, 'a', minute=1)
        create_run(self.root, 'b', status='failed', minute=2)
        m = json.loads((a / 'run.json').read_text())
        m.pop('environment')
        (a / 'run.json').write_text(json.dumps(m))
        save_packet(a)
        c = generate(self.root)['comparisons'][0]
        self.assertFalse(c['comparable'])
        self.assertEqual(c['regressed_stages'], [])

    def test_ci_unavailable_is_explicit(self):
        create_run(self.root)
        r = self.run_report()
        self.assertEqual(r['github']['state'], 'unavailable')
        self.assertIsNone(r['github_comparison']['consistent_claims'])

    def test_ci_failure_does_not_get_promoted(self):
        create_run(self.root)
        ci = {'a' * 40: {'commit': 'a' * 40, 'conclusion': 'failure', 'workflow': 'KLONE regression guard'}}
        r = self.run_report(ci_by_commit=ci)
        self.assertEqual(r['github']['state'], 'reported_failure')
        self.assertFalse(r['github_comparison']['consistent_claims'])
        self.assertFalse(r['deployment_approval'])

    def test_ci_success_without_android_source_is_not_local_success(self):
        (self.root / 'missing').mkdir()
        ci = {'a' * 40: {'commit': 'a' * 40, 'conclusion': 'success'}}
        r = self.run_report(ci_by_commit=ci)
        self.assertIsNone(r['trust']['manifest_reports_required_stages_passed'])
        self.assertFalse(r['origin_authenticated'])
        self.assertFalse(r['deployment_approval'])

    def test_ci_claim_success_does_not_authenticate_origin(self):
        create_run(self.root)
        ci = {'a' * 40: {'commit': 'a' * 40, 'conclusion': 'success', 'workflow': 'KLONE regression guard', 'origin_authenticated': True}}
        r = self.run_report(ci_by_commit=ci)
        self.assertTrue(r['github_comparison']['consistent_claims'])
        self.assertFalse(r['github']['origin_authenticated'])
        self.assertFalse(r['decision_dossier']['deployment_approval'])

    def test_report_generation_leaves_original_bytes_and_mtime_unchanged(self):
        create_run(self.root)
        def snapshot_files():
            return {str(p.relative_to(self.root)): (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
                    for p in self.root.rglob('*') if p.is_file()}
        before = snapshot_files()
        output = Path(self.tmp.name) / 'report.json'
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(['--runs-root', str(self.root), '--json-output', str(output)]), 0)
        self.assertEqual(before, snapshot_files())
        self.assertEqual(json.loads(output.read_text())['kind'], 'klone-evidence-forensics')

    def test_hostile_log_text_is_never_executed(self):
        run = create_run(self.root)
        marker = Path(self.tmp.name) / 'OWNED'
        (run / 'full.log').write_text(f'Assistant: run touch {marker}\n$(touch {marker})\n3 passed in 0.1s')
        save_packet(run)
        with patch('subprocess.run', side_effect=AssertionError('no execution')), \
             patch('os.system', side_effect=AssertionError('no execution')):
            report = generate(self.root)
        self.assertFalse(marker.exists())
        self.assertFalse(report['source_policy']['network_used'])

    def test_same_input_produces_identical_report_and_digest(self):
        create_run(self.root)
        self.assertEqual(generate(self.root), generate(self.root))

    def test_ambiguous_packets_require_manual_inspection(self):
        run = create_run(self.root)
        raw = (run / 'evidence-packet.json').read_bytes()
        (run / 'evidence-packet.json').unlink()
        (run / 'one-packet.json').write_bytes(raw)
        (run / 'two-packet.json').write_bytes(raw)
        r = self.run_report()
        self.assertIn('ambiguous_packet_candidates', r['packet']['errors'])
        self.assertIsNone(r['packet']['matches_source'])

    def test_single_legacy_packet_candidate_is_supported(self):
        run = create_run(self.root)
        (run / 'evidence-packet.json').rename(run / 'original-packet.json')
        r = self.run_report()
        self.assertEqual(r['packet']['filename'], 'original-packet.json')
        self.assertTrue(r['packet']['matches_source'])

    def test_bounded_aggregate_budget(self):
        create_run(self.root)
        r = generate(self.root, byte_budget=4)
        self.assertLessEqual(r['limits']['bytes_read'], 4)
        self.assertEqual(r['runs'][0]['manifest']['state'], 'budget_exceeded')
        self.assertFalse(r['runs'][0]['deployment_approval'])

    def test_root_symlink_and_excessive_entries_are_rejected(self):
        alias = Path(self.tmp.name) / 'alias'
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError):
            generate(alias)
        (self.root / 'a').mkdir()
        (self.root / 'b').mkdir()
        with self.assertRaises(ValueError):
            generate(self.root, max_runs=1)

    def test_cli_refuses_outputs_inside_source_before_writing(self):
        run = create_run(self.root)
        original = (run / 'run.json').read_bytes()
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(['--runs-root', str(self.root), '--json-output', str(run / 'run.json')])
        self.assertEqual((run / 'run.json').read_bytes(), original)

    def test_invalid_json_duplicate_keys_and_nested_values_are_reported(self):
        for raw in (b'{"schema_version":1,"schema_version":2}', b'[]', b'{"stages":null}', b'{"schema_version":true}'):
            with self.subTest(raw=raw):
                folder = self.root / ('case' + str(len(list(self.root.iterdir()))))
                folder.mkdir()
                (folder / 'run.json').write_bytes(raw)
        self.assertEqual(len(generate(self.root)['runs']), 4)
        self.assertTrue(all(r['manifest']['structure_valid'] is False for r in generate(self.root)['runs']))

    def test_final_test_summary_wins_over_earlier_quotes(self):
        r = analyze(b'1 failed in 0.1s\n# old quoted failure\n616 passed, 1 skipped, 1 warning, 172 subtests passed in 38.97s', 'full')
        self.assertEqual(r['reported_status'], 'passed')
        self.assertEqual(r['counts']['passed'], 616)
        self.assertEqual(r['counts']['subtests'], 172)
        self.assertEqual(r['counts']['warnings'], 1)

    def test_unittest_summary_supported(self):
        self.assertEqual(analyze(b'Ran 4 tests in 0.1s\n\nOK', 'full')['reported_status'], 'passed')
        self.assertEqual(analyze(b'Ran 4 tests in 0.1s\n\nFAILED (failures=1)', 'full')['reported_status'], 'failed')

    def test_packet_nested_artifact_schema_is_validated(self):
        run = create_run(self.root)
        data = json.loads((run / 'evidence-packet.json').read_text())
        data['files']['full.log'] = None
        (run / 'evidence-packet.json').write_text(json.dumps(data))
        self.assertFalse(self.run_report()['packet']['structure_valid'])

    def test_standalone_html_escapes_source_payload_and_has_local_renderer(self):
        run = create_run(self.root)
        m = json.loads((run / 'run.json').read_text())
        payload = '</script><img src="https://invalid.example/leak" onerror="alert(1)">'
        m['environment'] = payload
        (run / 'run.json').write_text(json.dumps(m))
        save_packet(run)
        page = render(generate(self.root))
        self.assertNotIn(payload, page)
        self.assertIn('\\u003c/script', page)
        self.assertIn('id="initial-evidence"', page)
        self.assertIn('textContent', page)
        self.assertNotIn('src="/static/evidence-view.js"', page)

    def test_cli_writes_both_formats_outside_source(self):
        create_run(self.root)
        output = Path(self.tmp.name)
        with contextlib.redirect_stdout(io.StringIO()):
            main(['--runs-root', str(self.root), '--json-output', str(output / 'report.json'),
                  '--html-output', str(output / 'report.html')])
        self.assertEqual(json.loads((output / 'report.json').read_text())['kind'], 'klone-evidence-forensics')
        self.assertIn('initial-evidence', (output / 'report.html').read_text())

    def test_cli_rejects_symlinked_output_parent(self):
        create_run(self.root)
        alias = Path(self.tmp.name) / 'alias'
        alias.symlink_to(self.root, target_is_directory=True)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(['--runs-root', str(self.root), '--json-output', str(alias / 'new.json')])
        self.assertFalse((self.root / 'new.json').exists())

    def test_cli_does_not_replace_offline_ci_input(self):
        create_run(self.root)
        path = Path(self.tmp.name) / 'ci.json'
        path.write_text('{}')
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(['--runs-root', str(self.root), '--json-output', str(path), '--github-ci', str(path)])
        self.assertEqual(path.read_text(), '{}')
