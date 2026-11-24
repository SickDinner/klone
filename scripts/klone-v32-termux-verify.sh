#!/data/data/com.termux/files/usr/bin/bash
# v3.2 LAB: verifies pinned commit and reruns focused/full regression.
# Usage: bash scripts/klone-v32-termux-verify.sh <exact-40-hex-commit>
set -eu

if [ "$#" -ne 1 ] || ! [[ "$1" =~ ^[0-9a-f]{40}$ ]]; then
  echo "Anna täsmällinen 40-merkkinen commit SHA" >&2
  exit 2
fi
EXPECTED="$1"
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
cd "$ROOT"
if [ "$(git rev-parse HEAD)" != "$EXPECTED" ]; then
  echo "Väärä commit, lopetetaan tekemättä muutoksia" >&2
  exit 1
fi
PY="$HOME/klone-next/.venv/bin/python"
if [ ! -x "$PY" ]; then
  echo "KLONE Python-virtuaaliympäristö puuttuu" >&2
  exit 1
fi
mkdir -p "$HOME/klone-var"
LOG=$(mktemp "$HOME/klone-var/klone-v32-full.XXXXXX.log")
set +e
PYTHONPATH="$ROOT/src" PYTHONDONTWRITEBYTECODE=1 "$PY" - <<'PY' >"$LOG" 2>&1
import sys
from pathlib import Path
import unittest

site = Path(sys.base_prefix) / "lib" / (
    f"python{sys.version_info.major}.{sys.version_info.minor}") / "site-packages"
if site.is_dir():
    sys.path.append(str(site))
import cryptography
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
private = Ed25519PrivateKey.generate()
private.public_key().verify(private.sign(b"KLONE-V32"), b"KLONE-V32")
print("CRYPTOGRAPHY:", cryptography.__version__, flush=True)
print("ED25519: OK", flush=True)
loader = unittest.defaultTestLoader
runner = unittest.TextTestRunner(verbosity=1)
target = loader.discover("tests", pattern="test_mission_control_live_v32.py")
print("V3.2 TESTEJÄ:", target.countTestCases(), flush=True)
if target.countTestCases() != 45:
    raise SystemExit("unexpected_v32_test_count")
r = runner.run(target)
if not r.wasSuccessful() or r.skipped:
    raise SystemExit("v32_target_failed_or_skipped")
all_tests = loader.discover("tests", pattern="test_*.py")
print("KOKO KLONE TESTEJÄ:", all_tests.countTestCases(), flush=True)
if all_tests.countTestCases() != 1507:
    raise SystemExit("unexpected_full_test_count")
r = runner.run(all_tests)
print("OHITETTUJA:", len(r.skipped), flush=True)
raise SystemExit(0 if r.wasSuccessful() and len(r.skipped) <= 2 else 1)
PY
RC=$?
set -e
printf '=== KLONE V3.2 ===\n'
grep -E '^CRYPTOGRAPHY:|^ED25519:|^V3.2 TESTEJÄ:|^KOKO KLONE TESTEJÄ:|^Ran [0-9]+ tests|^OK|^FAILED|^OHITETTUJA:' "$LOG" || true
printf 'PALUUKOODI: %s\nLOKI: %s\n' "$RC" "$LOG"
git status --short
if [ "$RC" -ne 0 ]; then tail -n 60 "$LOG"; fi
exit "$RC"
