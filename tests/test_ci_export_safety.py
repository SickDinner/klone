"""Bounded GitHub transport and new-only exports preserve original evidence."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

from forensics_fixture import create_run
from test_evidence_github_bridge import run, listing, SHA
from test_evidence_cross_environment import android, github
from klone.evidence_github_bridge import fetch, normalize, main, MAX_RESPONSE, _NoRedirect
from klone.evidence_io import new_output_path, write_new_report, directory_handle
from klone.evidence_cross_environment import compare, main as cross_main
from klone.evidence_one_command import main as one_main
from klone.evidence_forensics import generate


class BridgeTransportTests(unittest.TestCase):
    def response(self, raw):
        class Response(io.BytesIO):
            def __init__(self):
                super().__init__(raw)
                self.read_sizes = []
            def read(self, size=-1):
                self.read_sizes.append(size)
                return super().read(size)
        return Response()

    def fetch_response(self, raw):
        response = self.response(raw)
        with patch('klone.evidence_github_bridge.urllib.request.build_opener') as builder:
            builder.return_value.open.return_value = response
            result = fetch('SickDinner/klone', SHA)
            self.assertIsInstance(builder.call_args.args[0], _NoRedirect)
            request = builder.return_value.open.call_args.args[0]
            self.assertEqual(request.full_url, 'https://api.github.com/repos/SickDinner/klone/actions/runs?per_page=100&head_sha=' + SHA)
            self.assertEqual(builder.return_value.open.call_args.kwargs['timeout'], 15)
        return result, response.read_sizes

    def test_transport_reads_a_bounded_strict_snapshot(self):
        result, sizes = self.fetch_response(json.dumps(listing([run()])).encode())
        self.assertEqual(sizes, [MAX_RESPONSE + 1])
        self.assertEqual(result['conclusion'], 'success')
        self.assertTrue(result['listing_complete'])
        self.assertFalse(result['job_matrix_verified'])
        self.assertFalse(result['origin_authenticated'])

    def test_large_and_invalid_json_rejected(self):
        for raw in (b' ' * (MAX_RESPONSE + 1), b'{broken', b'[]', b'{"x":1,"x":2}', b'{"x":NaN}', b'\xff'):
            with self.subTest(raw=raw[:20]), self.assertRaises(ValueError):
                self.fetch_response(raw)

    def test_redirect_cannot_forward_authorization(self):
        request = urllib.request.Request('https://api.github.com/repos/SickDinner/klone/actions/runs',
                                         headers={'Authorization': 'Bearer SYNTHETIC_SECRET'})
        with self.assertRaisesRegex(ValueError, 'redirects are not allowed'):
            _NoRedirect().redirect_request(request, io.BytesIO(), 302, 'Found', {}, 'https://other.invalid/')

    def test_invalid_token_never_reaches_transport(self):
        for token in ('secret\nInjected: value', 'secret\rvalue', 'a b', '\x00', 1):
            with self.subTest(token_type=type(token).__name__), patch('klone.evidence_github_bridge.urllib.request.build_opener') as builder:
                with self.assertRaises(ValueError):
                    fetch('SickDinner/klone', SHA, token)
                builder.assert_not_called()

    def test_network_error_never_echoes_credentials(self):
        token = 'SYNTHETIC_SECRET'
        with patch('klone.evidence_github_bridge.urllib.request.build_opener') as builder:
            builder.return_value.open.side_effect = urllib.error.URLError(token)
            with self.assertRaises(ValueError) as error:
                fetch('SickDinner/klone', SHA, token)
        self.assertNotIn(token, str(error.exception))
        self.assertIn('URLError', str(error.exception))

    def test_incomplete_or_ambiguous_listing_never_falls_back_to_green(self):
        for payload in ({'total_count': 2, 'workflow_runs': [run()]},
                        {'workflow_runs': [run()]}, {'total_count': True, 'workflow_runs': [run()]},
                        listing([run(), run()]), listing([None]),
                        listing([run(id=n + 1) for n in range(101)])):
            with self.subTest(payload_size=len(str(payload))), self.assertRaises(ValueError):
                normalize(payload, SHA)

    def test_invalid_newer_matching_identity_never_falls_back(self):
        changes = [{'id': True}, {'id': -1}, {'run_attempt': True}, {'run_attempt': 0},
                   {'repository': {'full_name': 'other/repo'}}, {'path': '.github/workflows/other.yml'},
                   {'status': []}, {'conclusion': {}}, {'status': 'unknown'}, {'conclusion': 'unknown'}]
        for changed in changes:
            newer = run(id=2)
            newer.update(changed)
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                normalize(listing([run(id=1), newer]), SHA)

    def test_newer_pending_or_failed_run_prevents_old_success(self):
        for changes, expected in (({'status': 'in_progress', 'conclusion': 'success'}, None),
                                  ({'conclusion': 'failure'}, 'failure')):
            result = normalize(listing([run(id=1), run(id=2, **changes)]), SHA)
            self.assertEqual(result['run_id'], 2)
            self.assertEqual(result['conclusion'], expected)


class ExportSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base / 'runs'
        self.run = create_run(self.root)
        self.output = self.base / 'exports' / 'ci.json'

    def args(self):
        return ['--commit', SHA, '--output', str(self.output), '--runs-root', str(self.root)]

    def cli_error(self, function, args):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            function(args)
        self.assertEqual(error.exception.code, 2)

    def test_existing_export_is_not_replaced_or_fetched(self):
        self.output.parent.mkdir()
        self.output.write_text('ORIGINAL')
        with patch('klone.evidence_github_bridge.fetch') as remote:
            self.cli_error(main, self.args())
        remote.assert_not_called()
        self.assertEqual(self.output.read_text(), 'ORIGINAL')

    def test_cannot_add_export_inside_source_evidence_or_git(self):
        for path in (self.run / 'ci.json', self.root / 'new' / 'ci.json',
                     self.base / '.git' / 'ci.json', self.base / '.GIT' / 'ci.json'):
            args = self.args()
            args[3] = str(path)
            with patch('klone.evidence_github_bridge.fetch') as remote:
                self.cli_error(main, args)
            remote.assert_not_called()
            self.assertFalse(path.exists())

    def test_symlink_destination_and_parent_are_rejected(self):
        self.output.parent.mkdir()
        target = self.base / 'original'
        target.write_text('ORIGINAL')
        link = self.base / 'linked-parent'
        try:
            self.output.symlink_to(target)
            link.symlink_to(self.output.parent, target_is_directory=True)
        except OSError:
            self.skipTest('symlink creation unavailable')
        for path in (self.output, link / 'new.json'):
            with self.assertRaises(ValueError):
                write_new_report(path, 'CHANGED', self.root)
        self.assertEqual(target.read_text(), 'ORIGINAL')
        self.assertFalse((self.output.parent / 'new.json').exists())

    def test_raced_in_destination_is_never_overwritten(self):
        @contextlib.contextmanager
        def race(path, **kwargs):
            with directory_handle(path, **kwargs) as descriptor:
                self.output.write_text('RACED-IN')
                yield descriptor
        with patch('klone.evidence_io.directory_handle', side_effect=race):
            with self.assertRaises(FileExistsError):
                write_new_report(self.output, 'CHANGED', self.root)
        self.assertEqual(self.output.read_text(), 'RACED-IN')

    def test_portable_exclusive_writer_also_preserves_existing_files(self):
        with patch('klone.evidence_io._DIR_FD', False):
            write_new_report(self.output, 'ORIGINAL', self.root)
            with self.assertRaises(ValueError):
                write_new_report(self.output, 'CHANGED', self.root)
        self.assertEqual(self.output.read_text(), 'ORIGINAL')

    def test_forensics_map_is_directly_consumable_and_sources_unchanged(self):
        paths = [p for p in self.root.rglob('*') if p.is_file()]
        before = {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in paths}
        normalized = normalize(listing([run()]), SHA)
        with patch('klone.evidence_github_bridge.fetch', return_value=normalized), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(self.args() + ['--forensics-map']), 0)
        report = generate(self.root, ci_by_commit=json.loads(self.output.read_text()))
        github_run = report['runs'][0]['github']
        self.assertEqual(github_run['run_id'], 42)
        self.assertTrue(github_run['listing_complete'])
        self.assertFalse(github_run['job_matrix_verified'])
        self.assertTrue(report['runs'][0]['github_comparison']['consistent_claims'])
        self.assertFalse(report['deployment_approval'])
        self.assertEqual(before, {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in paths})

    def test_failed_ci_export_stays_failed_and_is_still_saved(self):
        normalized = normalize(listing([run(conclusion='failure')]), SHA)
        with patch('klone.evidence_github_bridge.fetch', return_value=normalized), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(self.args()), 2)
        self.assertEqual(json.loads(self.output.read_text())['conclusion'], 'failure')

    def test_network_failure_creates_no_export(self):
        with patch('klone.evidence_github_bridge.fetch', side_effect=ValueError('unavailable')):
            self.cli_error(main, self.args())
        self.assertFalse(self.output.exists())

    def test_one_command_output_is_validated_before_network_or_source_inspection(self):
        target = self.run / 'new.json'
        with patch('klone.evidence_one_command.run') as action:
            self.cli_error(one_main, ['--run-directory', str(self.run), '--output', str(target)])
        action.assert_not_called()
        self.assertFalse(target.exists())

    def test_cross_environment_does_not_replace_input(self):
        a, g = self.base / 'android.json', self.base / 'github.json'
        a.write_text(json.dumps(android()))
        g.write_text(json.dumps(github()))
        before = a.read_bytes()
        self.cli_error(cross_main, ['--android-status', str(a), '--github-ci', str(g), '--output', str(a)])
        self.assertEqual(a.read_bytes(), before)

    def test_cross_environment_json_is_strict_and_bounded(self):
        a, g = self.base / 'android.json', self.base / 'github.json'
        g.write_text(json.dumps(github()))
        for raw in ('{"commit":"a","commit":"b"}', '{"x":NaN}', ' ' * 131073):
            a.write_text(raw)
            self.cli_error(cross_main, ['--android-status', str(a), '--github-ci', str(g)])

    def test_explicit_pending_or_incomplete_ci_blocks_forensics_comparison(self):
        for changes, reason in (({'run_status': 'in_progress'}, 'github_ci_not_completed'),
                                ({'listing_complete': False}, 'github_ci_listing_incomplete'),
                                ({'repository': 'other/repo'}, 'unexpected_repository'),
                                ({'workflow_path': 'other.yml'}, 'unexpected_workflow_path')):
            ci = github(**changes)
            self.assertIn(reason, compare(android(), ci)['errors'])
            record = generate(self.root, ci_by_commit={SHA:ci})['runs'][0]
            self.assertFalse(record['github_comparison']['consistent_claims'])
            self.assertIn(reason, record['github_comparison']['errors'])
            self.assertFalse(record['deployment_approval'])


if __name__ == '__main__':
    unittest.main()
