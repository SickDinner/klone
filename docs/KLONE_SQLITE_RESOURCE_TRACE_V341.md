# KLONE v3.4.1 – SQLite ResourceWarning origin investigation (LAB)

2026-11-24. Base: PR #205, commit `6066c0211be6fe1ae144bf65b8e470e4718180c9`.

## Observations, not assumptions

- Android full v3.1 run initially emitted three `ResourceWarning: unclosed database` messages while importing Starlette routing. Source allocation was **not** identified. Warning emission line may be a garbage collection site, not where the connection was opened.
- A v3.4 memory-only trace of `test_memory_phase_2b3.py` ran **4 tests, OK** with `PYTHONTRACEMALLOC=25` and `PYTHONWARNINGS=always::ResourceWarning`; original full log was searched and contained **no** SQLite/ResourceWarning messages. The leak is therefore **not reproduced by those four tests**, not disproved globally.
- `KloneRepository.connection()` uses `finally: conn.close()`; `ResearchMemory._connect()` also closes; `research_audit_outbox` uses `contextlib.closing`. Do **not** alter code without a reproducible failing case.

## New diagnostic tracer

`tools/trace_sqlite_resources_v341.py` selects only fixed test-module allowlists for `memory` (10 files), `research` (5) and `approval` (5). Each execution:

1. Refuses a Git checkout different from the supplied 40-digit commit.
2. Runs the selected tests with `ResourceWarning` capture and 15-frame `tracemalloc` tracing.
3. Runs `gc.collect()` twice before leaving warning capture.
4. Outputs a bounded JSON report with summary counts and warning origin lines, and the **allocation traceback only if Python provides the warning source**. It never claims origin if no trace is available.
5. Exit codes: `0` = tests passed and no ResourceWarnings observed; `2` = test failure; `3` = ResourceWarning observed; invalid inputs fail earlier. **Zero warnings do not prove absence of connection leaks.**

The tracer never selects or opens the live KLONE SQLite database itself; tests may create and modify their own temporary fixtures. It does not start/stop a service, install anything, or call the network.

### Termux invocation, each group in its own process

```sh
cd "$HOME/klone-v341-trace"
SHA="<PINNED_SHA_FROM_PR>"
PY="$HOME/klone-next/.venv/bin/python"
mkdir -p "$HOME/klone-var"
for group in memory research approval; do
  echo "=== $group ==="
  PYTHONDONTWRITEBYTECODE=1 "$PY" tools/trace_sqlite_resources_v341.py \
    --group "$group" --expected-commit "$SHA" \
    > "$HOME/klone-var/sqlite-v341-$group.json"
  rc=$?
  echo "group=$group exit_code=$rc log=$HOME/klone-var/sqlite-v341-$group.json"
done
```

Do not use `set -e` for this exploratory loop without capturing return codes: exit 3 means a diagnostic warning was found and subsequent groups should still run.

### Limits

- Warnings from long-lived objects may surface only at interpreter shutdown, after this capture; without an allocation source, `tracemalloc` cannot infer an origin.
- The 20-module selected test matrix is not the full 1583-test suite. Repeat with a broader isolated run **only if** all selected groups are clean and the warning can still be reproduced.
- A warning can be caused by a third-party test fixture and need not be a KLONE core bug. A corrected production connection lifecycle must have a reproducer and a failing regression before editing.
