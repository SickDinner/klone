"""Synthetic v2 manifests only; never used to upgrade historical runs."""
from klone.evidence_run_context import context_id, digest


def environment():
    return {"python_version": "3.13.13", "implementation": "CPython", "platform": "synthetic-test",
            "machine": "test-machine", "system_release": "fixture", "sysconfig_platform": "fixture",
            "packages": {"pytest": "9.2.0"}}


def upgrade(manifest, *, cwd="/synthetic-checkout", python="/synthetic-venv/bin/python"):
    manifest["schema_version"] = 2
    manifest["environment"] = environment()
    commands = {n: [python, "-B", "-m", "pytest", n] for n in manifest["stages"]}
    commands["torch_probe"] = None
    execution = {"context_version": 1, "cwd": cwd, "python_executable": python,
                 "python_prefix": "/synthetic-venv", "virtualenv_reported": True,
                 "commands": commands, "environment_overrides": {"PYTHONPATH": cwd + "/src", "PYTHONDONTWRITEBYTECODE": "1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"},
                 "timeout_seconds": 240, "test_suite_before": {"sha256": "c" * 64, "file_count": 5},
                 "test_suite_after": {"sha256": "c" * 64, "file_count": 5},
                 "collector_sha256": "d" * 64, "collector_after_sha256": "d" * 64,
                 "environment_after_sha256": digest(manifest["environment"]), "context_consistent": True}
    execution["comparison_id"] = context_id(manifest["environment"], execution)
    manifest["execution"] = execution
    for stage in manifest["stages"].values():
        stage.update(capture_complete=True, timed_out=False)
    manifest["collection_complete"] = True
    return manifest
