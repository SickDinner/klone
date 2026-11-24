#!/data/data/com.termux/files/usr/bin/bash
# v3.3 LAB: exact-pin, read-only test runner. Does not start services or touch DB.
set -eu
if [ "$#" -ne 1 ] || ! [[ "$1" =~ ^[0-9a-f]{40}$ ]]; then
  echo 'Anna täsmällinen 40-merkkinen commit SHA' >&2
  exit 2
fi
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
cd "$ROOT"
if [ "$(git rev-parse HEAD)" != "$1" ]; then
  echo 'Väärä commit – keskeytetään' >&2
  exit 1
fi
PY="$HOME/klone-next/.venv/bin/python"
if [ ! -x "$PY" ]; then
  echo 'KLONE venv puuttuu' >&2
  exit 1
fi
mkdir -p "$HOME/klone-var"
LOG=$(mktemp "$HOME/klone-var/klone-v33-full.XXXXXX.log")
set +e
PYTHONPATH="$ROOT/src" PYTHONDONTWRITEBYTECODE=1 "$PY" - <<'PY' > "$LOG" 2>&1
import sys
from pathlib import Path
import unittest

site = Path(sys.base_prefix) / "lib" / (
    f"python{sys.version_info.major}.{sys.version_info.minor}") / "site-packages"
if site.is_dir():
    sys.path.append(str(site))
import cryptography
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
key = Ed25519PrivateKey.generate()
key.public_key().verify(key.sign(b"KLONE-V33"), b"KLONE-V33")
print("CRYPTOGRAPHY:", cryptography.__version__, flush=True)
print("ED25519: OK", flush=True)
loader = unittest.defaultTestLoader
runner = unittest.TextTestRunner(verbosity=1)
focused = loader.discover("tests", pattern="test_mission_control_dashboard_v33.py")
focused_count = focused.countTestCases()
print("V3.3 TESTEJÄ:", focused_count, flush=True)
if focused_count != 34:
    raise SystemExit("v33_new_test_count_mismatch")
r = runner.run(focused)
if not r.wasSuccessful() or r.skipped:
    raise SystemExit(1)

all_tests = loader.discover("tests", pattern="test_*.py")

def iter_cases(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from iter_cases(item)
        else:
            yield item

cases = list(iter_cases(all_tests))
ids = [case.id() for case in cases]
duplicates = sorted({test_id for test_id in ids if ids.count(test_id) > 1})
print("KOKO KLONE TESTEJÄ:", len(cases), flush=True)
print("YKSIKÄSITTEISIÄ TESTITUNNISTEITA:", len(set(ids)), flush=True)
if not cases or len(cases) < focused_count:
    raise SystemExit("full_suite_discovery_incomplete")
if duplicates:
    print("DUPLIKAATIT TESTITUNNISTEET:", duplicates, flush=True)
    raise SystemExit("duplicate_test_discovery")
r = runner.run(all_tests)
print("OHITETTUJA:", len(r.skipped), flush=True)
raise SystemExit(0 if r.wasSuccessful() and len(r.skipped) <= 2 else 1)
PY
RC=$?
set -e
printf '=== KLONE V3.3 ===\n'
grep -E '^CRYPTOGRAPHY:|^ED25519:|^V3.3 TESTEJÄ:|^KOKO KLONE TESTEJÄ:|^YKSIKÄSITTEISIÄ TESTITUNNISTEITA:|^Ran [0-9]+ tests|^OK|^FAILED|^OHITETTUJA:|^DUPLIKAATIT TESTITUNNISTEET:' "$LOG" || true
printf 'PALUUKOODI: %s\nLOKI: %s\n' "$RC" "$LOG"
git status --short
if [ "$RC" -ne 0 ]; then tail -n 70 "$LOG"; fi
exit "$RC"
PY