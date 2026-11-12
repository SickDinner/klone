#!/usr/bin/env bash
# KLONE safe sync: never reset/clean the user's working checkout.
set -Eeuo pipefail
ROOT="${KLONE_ROOT:-$HOME/klone-next}"
TEST_ROOT="${KLONE_TEST_ROOT:-$HOME/klone-sync-test}"
PY="${KLONE_PYTHON:-$ROOT/.venv/bin/python}"
RUN_BASE="${KLONE_RUN_BASE:-$HOME/klone-var/test-runs}"
REMOTE="${KLONE_REMOTE:-origin}"
BRANCH="${KLONE_BRANCH:-main}"
if [[ ! -x "$PY" ]]; then echo "Python missing: $PY" >&2; exit 2; fi
if ! git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Not a git checkout: $ROOT" >&2; exit 2
fi
git -C "$ROOT" fetch "$REMOTE" "$BRANCH"
TARGET="$(git -C "$ROOT" rev-parse --verify "refs/remotes/$REMOTE/$BRANCH^{commit}")"
if [[ -e "$TEST_ROOT" ]]; then
  if ! git -C "$TEST_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "Existing test path is not a git worktree: $TEST_ROOT" >&2; exit 2
  fi
  if [[ -n "$(git -C "$TEST_ROOT" status --porcelain)" ]]; then
    echo "Refusing to switch dirty test worktree: $TEST_ROOT" >&2; exit 2
  fi
  git -C "$TEST_ROOT" switch --detach "$TARGET"
else
  git -C "$ROOT" worktree add --detach "$TEST_ROOT" "$TARGET"
fi
if [[ ! -e "$TEST_ROOT/.venv" ]]; then
  ln -s "$ROOT/.venv" "$TEST_ROOT/.venv"
fi
if [[ -n "$(git -C "$TEST_ROOT" status --porcelain)" ]]; then
  echo "Test worktree dirty after setup; add local venv to worktree exclude manually" >&2
  exit 2
fi
RUN_DIR="$RUN_BASE/sync-$(date +%Y%m%d-%H%M%S)-${TARGET:0:12}"
if [[ -e "$RUN_DIR" ]]; then echo "Run directory exists: $RUN_DIR" >&2; exit 2; fi
mkdir -p "$RUN_DIR"
export PYTHONPATH="$TEST_ROOT/src"
echo "KLONE target: $TARGET"
set +e
"$PY" "$TEST_ROOT/tools/termux_evidence_battery.py" \
  --root "$TEST_ROOT" --output "$RUN_DIR" --timeout 240
battery_status=$?
set -e
if [[ -f "$RUN_DIR/run.json" ]]; then
  "$PY" -m klone.evidence_network pack \
    --run-directory "$RUN_DIR" --output "$RUN_DIR/evidence-packet.json"
  "$PY" -m klone.evidence_network verify \
    --run-directory "$RUN_DIR" --packet "$RUN_DIR/evidence-packet.json"
else
  echo "No run.json; test command failed before producing evidence" >&2
  exit 2
fi
echo "Evidence directory: $RUN_DIR"
echo "Battery exit status: $battery_status"
exit "$battery_status"
