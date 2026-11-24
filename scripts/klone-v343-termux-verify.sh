#!/data/data/com.termux/files/usr/bin/bash
# KLONE v3.4.3: pinned Android/Termux fixture-closure and full regression.
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
if [ ! -x "$PY" ]; then echo 'Termux-testien Python puuttuu' >&2; exit 1; fi
mkdir -p "$HOME/klone-var"
LOG="$(mktemp "$HOME/klone-var/klone-v343-full.XXXXXX.log")"
set +e
PYTHONPATH="$ROOT/src" PYTHONDONTWRITEBYTECODE=1 "$PY" - <<'PY' > "$LOG" 2>&1
import sys
from pathlib import Path
import unittest
site = Path(sys.base_prefix) / 'lib' / f'python{sys.version_info.major}.{sys.version_info.minor}' / 'site-packages'
if site.is_dir(): sys.path.append(str(site))
loader = unittest.defaultTestLoader
runner = unittest.TextTestRunner(verbosity=1)
focus = loader.discover('tests', pattern='test_sqlite_fixture_closure_v343.py')
print("V3.4.3 TESTEJÄ:", focus.countTestCases(), flush=True)
if focus.countTestCases() != 1: raise SystemExit("focused_test_count_mismatch")
f = runner.run(focus)
if not f.wasSuccessful() or f.skipped: raise SystemExit(1)
suite = loader.discover('tests', pattern='test_*.py')
print("KOKO KLONE TESTEJÄ:", suite.countTestCases(), flush=True)
if suite.countTestCases() != 1611: raise SystemExit("full_test_count_mismatch")
r = runner.run(suite)
print("OHITETTUJA:", len(r.skipped), flush=True)
raise SystemExit(0 if r.wasSuccessful() and len(r.skipped) <= 2 else 1)
PY
RC=$?
set -e
echo '=== KLONE V3.4.3 ==='
grep -E '^V3.4.3 TESTEJÄ:|^KOKO KLONE TESTEJÄ:|^Ran [0-9]+ tests|^OK|^FAILED|^OHITETTUJA:' "$LOG" || true
printf 'PALUUKOODI: %s\nLOKI: %s\n' "$RC" "$LOG"
if [ "$RC" -ne 0 ]; then tail -n 60 "$LOG"; fi
exit "$RC"
