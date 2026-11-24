#!/data/data/com.termux/files/usr/bin/bash
# Explicit, non-destructive SQLite ResourceWarning trace for temporary test DBs.
# This does not touch the running KLONE database; tests still have their own fixtures.
set -eu
if [ "$#" -ne 1 ] || ! [[ "$1" =~ ^[0-9a-f]{40}$ ]]; then
  echo 'Anna tarkka 40-merkkinen commit SHA' >&2; exit 2
fi
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
cd "$ROOT"
if [ "$(git rev-parse HEAD)" != "$1" ]; then
  echo 'Väärä commit – keskeytetään' >&2; exit 1
fi
PY="$HOME/klone-next/.venv/bin/python"
if [ ! -x "$PY" ]; then echo 'Testiympäristö puuttuu' >&2; exit 1; fi
mkdir -p "$HOME/klone-var"
LOG=$(mktemp "$HOME/klone-var/klone-v34-sqlite-trace.XXXXXX.log")
set +e
PYTHONPATH="$ROOT/src" PYTHONTRACEMALLOC=25 PYTHONWARNINGS=always::ResourceWarning \
PYTHONDONTWRITEBYTECODE=1 "$PY" - <<'PY' > "$LOG" 2>&1
import sys, unittest
from pathlib import Path
site = Path(sys.base_prefix) / 'lib' / f'python{sys.version_info.major}.{sys.version_info.minor}' / 'site-packages'
if site.is_dir(): sys.path.append(str(site))
loader = unittest.defaultTestLoader
suite = loader.discover('tests', pattern='test_memory_phase_2b3.py')
print('TRACE TESTEJÄ:', suite.countTestCases(), flush=True)
if suite.countTestCases() < 1:
    raise SystemExit('tests_not_discovered')
r = unittest.TextTestRunner(verbosity=1).run(suite)
raise SystemExit(0 if r.wasSuccessful() else 1)
PY
RC=$?
set -e
echo '=== SQLite-trace ==='
grep -E '^TRACE TESTEJÄ:|^Ran [0-9]+ tests|^OK|^FAILED|^ResourceWarning:|^  File ' "$LOG" | head -n 120 || true
printf 'PALUUKOODI: %s\nLOKI: %s\n' "$RC" "$LOG"
exit "$RC"
