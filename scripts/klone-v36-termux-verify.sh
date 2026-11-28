#!/data/data/com.termux/files/usr/bin/bash
# KLONE v3.6 LAB: exact-commit, bounded verification. No service control.
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
  echo 'KLONE venv puuttuu: $PY' >&2
  exit 1
fi
mkdir -p "$HOME/klone-var"
LOG="$(mktemp "$HOME/klone-var/klone-v36-termux.XXXXXX.log")"

set +e
PYTHONPATH="$ROOT/src" PYTHONDONTWRITEBYTECODE=1 "$PY" - <<'PY' >"$LOG" 2>&1
import sys
import unittest
from pathlib import Path

site = Path(sys.base_prefix) / "lib" / (
    f"python{sys.version_info.major}.{sys.version_info.minor}"
) / "site-packages"
if site.is_dir():
    sys.path.append(str(site))

try:
    import cryptography
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
except ImportError as exc:
    print("CRYPTOGRAPHY: puuttuu:", type(exc).__name__, flush=True)
    raise SystemExit(2)

key = Ed25519PrivateKey.generate()
key.public_key().verify(key.sign(b"KLONE-V36"), b"KLONE-V36")
print("CRYPTOGRAPHY:", cryptography.__version__, flush=True)
print("ED25519: OK", flush=True)

def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item

loader = unittest.defaultTestLoader
runner = unittest.TextTestRunner(verbosity=1)
focused = loader.discover("tests", pattern="test_service_identity_receipts_v35.py")
focused_cases = list(flatten(focused))
print("V3.6 IDENTITY/AUDIT TESTEJÄ:", len(focused_cases), flush=True)
if len(focused_cases) != 17:
    raise SystemExit("focused_test_count_mismatch")
result = runner.run(unittest.TestSuite(focused_cases))
if not result.wasSuccessful() or result.skipped:
    raise SystemExit(1)

all_tests = loader.discover("tests", pattern="test_*.py")
all_cases = list(flatten(all_tests))
ids = [case.id() for case in all_cases]
if len(ids) != len(set(ids)):
    duplicates = sorted({test_id for test_id in ids if ids.count(test_id) > 1})
    print("DUPLICATE TEST IDS:", duplicates[:20], flush=True)
    raise SystemExit("duplicate_test_ids")
print("KOKO KLONE TESTEJÄ:", len(all_cases), flush=True)
result = runner.run(unittest.TestSuite(all_cases))
print("OHITETTUJA:", len(result.skipped), flush=True)
raise SystemExit(0 if result.wasSuccessful() and len(result.skipped) <= 2 else 1)
PY
RC=$?
set -e

printf '=== KLONE v3.6 Termux -tarkistus ===\n'
grep -E '^CRYPTOGRAPHY:|^ED25519:|^V3.6 IDENTITY/AUDIT TESTEJÄ:|^KOKO KLONE TESTEJÄ:|^Ran [0-9]+ tests|^OK|^FAILED|^OHITETTUJA:|^DUPLICATE TEST IDS:' "$LOG" || true
printf 'PALUUKOODI: %s\nLOKI: %s\n' "$RC" "$LOG"
git status --short
if [ "$RC" -ne 0 ]; then
  tail -n 70 "$LOG"
fi
exit "$RC"
