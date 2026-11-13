#!/usr/bin/env bash
# KLONE read-only Evidence Forensics validation on Android/Termux.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${KLONE_PYTHON:-$HOME/klone-next/.venv/bin/python}"
RUNS="${KLONE_RUNS_ROOT:-$HOME/klone-var/test-runs}"
OUT="${KLONE_FORENSICS_OUTPUT:-$HOME/klone-var/evidence-forensics.json}"
cd "$ROOT"
test -x "$PY" || { echo "Python environment missing: $PY" >&2; exit 1; }
test -d "$RUNS" || { echo "Runs root missing: $RUNS" >&2; exit 1; }
echo "== Focused evidence tests =="
PYTHONPATH=src "$PY" -m pytest -q tests/test_evidence_forensics.py tests/test_evidence_artifact_inspector.py
echo "== Full regression suite =="
PYTHONPATH=src "$PY" -m pytest -q
echo "== Read-only forensic report =="
PYTHONPATH=src "$PY" -m klone.evidence_forensics --runs-root "$RUNS" --output "$OUT"
echo "Report: $OUT"
