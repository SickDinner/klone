#!/usr/bin/env bash
# Full KLONE test battery, preserving logs even if a test fails.
set -uo pipefail
cd "${KLONE_ROOT:-$HOME/klone-next}" || exit 2
PY="$PWD/.venv/bin/python"
[[ -x "$PY" ]] || { echo "Missing virtualenv"; exit 2; }
OUT="$HOME/klone-var/test-runs/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT"
export PYTHONPATH="$PWD/src"
run() {
  local name="$1"; shift
  echo "=== $name ==="
  "$@" > "$OUT/$name.log" 2>&1
  local rc=$?
  echo "$name: exit=$rc" | tee -a "$OUT/summary.txt"
  tail -n 12 "$OUT/$name.log"
  return 0
}
run syntax "$PY" -m compileall -q src/klone
run cognition "$PY" -m unittest discover -s tests -p 'test_cognition*.py' -v
run full "$PY" -m pytest -q
run local_deploy "$PY" -m pytest -q tests/test_local_deploy.py
run torch_probe "$PY" scripts/klone-local-torch-demo.py
echo "=== RESULTS: $OUT ==="
cat "$OUT/summary.txt"
if grep -Eq 'exit=[1-9]' "$OUT/summary.txt"; then
  echo "SOME TESTS FAILED; inspect logs. Do not merge."
  exit 1
fi
echo "ALL TEST COMMANDS PASSED"
