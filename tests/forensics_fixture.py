"""Synthetic fixture only: no historical evidence is included or regenerated."""
import json
from pathlib import Path
from klone.evidence_network import STAGES, build_packet


def create_run(root: Path, name='a', status='passed', minute=1, packet=True):
    directory = root / name
    directory.mkdir(parents=True)
    manifest = {"schema_version": 1,
                "before": {"commit": 'a' * 40, "dirty": False},
                "after": {"commit": 'a' * 40, "dirty": False},
                "started_at": f'2026-11-12T18:{minute:02d}:00Z',
                "completed_at": f'2026-11-12T18:{minute:02d}:30Z',
                "stages": {n: {"status": 'passed', "exit_code": 0} for n in STAGES},
                "required_tests_passed": status == 'passed', "checkout_consistent": True,
                "overall": status, "device_identity_verified": False,
                "deployment_approval": False,
                "environment": {"platform": 'synthetic-test', "suite": 'fixture-v1'}}
    manifest['stages']['full'] = {"status": status, "exit_code": 0 if status == 'passed' else 1}
    manifest['stages']['torch_probe'] = {"status": 'not_present', "exit_code": None}
    (directory / 'run.json').write_text(json.dumps(manifest))
    for stage in STAGES:
        text = ('1 failed, 2 passed in 0.04s' if stage == 'full' and status == 'failed'
                else '3 passed in 0.04s')
        if stage == 'torch_probe':
            text = 'Optional torch demo not present in this checkout'
        (directory / (stage + '.log')).write_text('' if stage == 'syntax' else text)
    if packet:
        save_packet(directory)
    return directory


def save_packet(directory):
    (directory / 'evidence-packet.json').write_text(json.dumps(build_packet(directory)))
