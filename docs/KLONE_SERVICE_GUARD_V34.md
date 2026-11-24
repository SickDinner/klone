# KLONE v3.4 — Service Guard and SQLite diagnosis (LAB, 2026-11-24)

Base: PR #204, exact SHA `bda0909954b6a074fc30de2571d0516afc9e8046`.

## Verified user environment (source: user's on-device observations)

- Main KLONE API listens on `127.0.0.1:8000`; its process is working from `~/klone-next`. **Do not stop, restart, rebind, or upgrade this service by running the new module.**
- Legacy endpoint ports 8001, 8010, 8011, 8012, 8020 did not listen in the observed snapshot. This does not prove those services are required, absent, or safe to start.
- Two old `klone_control.py` launchers have `owner_debug=True` defaults. They MUST NOT be used for the new service guard.
- The v3.3 dashboard on 8011 is a standalone local-only and database-free renderer; use its existing explicit foreground runner.

## v3.4 additions

`klone.service_guard_v34` composes v3.2's bounded, fixed-port health snapshot with a strict service-role manifest. The only actions it **describes** are:

- **8000/main-api:** preserve the existing externally managed primary process; if unhealthy, inspect manually, never restart automatically.
- **8011/mission-control-ui:** an explicit foreground `--serve-dashboard` invocation delegates to the existing v3.3 server. The server itself atomically binds only `127.0.0.1:8011` and refuses to start if the bind fails. A failed HTTP probe is **not** evidence the port is free.
- **8001/8010/8012/8020:** optional legacy endpoints, with no reviewed launcher or automatic restart. Their absence is listed, but is not falsely counted as main-API failure.

The new service triage recomputes counts and checks the v3.2 snapshot schema and SHA-256. Neither digest is a signature or proof of source identity. A caller-supplied expected commit is a **claim**, not checkout authentication.

There is **no** socket scan beyond the fixed six localhost endpoints; no configurable host/port, external web fetch, database reading/writing, PID signaling, process spawning, daemonization, key copying, API tokens, scheduling, or production authorization.

## Verify on Termux

1. Fetch the exact v3.4 commit into a **new** worktree.
2. Run `bash scripts/klone-v34-termux-verify.sh <exact-full-commit-sha>`.
3. Read-only inspection of local endpoints:

```sh
cd ~/klone-v34-service-guard
PYTHONPATH="$PWD/src" "$HOME/klone-next/.venv/bin/python" \
  -m klone.service_guard_v34 --inspect-local \
  --expected-commit "$(git rev-parse HEAD)"
```

4. If desired, start only the new dashboard on 8011 in **another foreground Termux session**:

```sh
cd ~/klone-v34-service-guard
PYTHONPATH="$PWD/src" "$HOME/klone-next/.venv/bin/python" \
  -m klone.service_guard_v34 --serve-dashboard
```

View `http://127.0.0.1:8011/` on the same device. Stop by Ctrl+C. A second launch will fail with a bind error instead of replacing the first. This dashboard is not authenticated for untrusted local processes and must not be externally exposed.

## SQLite warnings — isolate, do not guess

The earlier `ResourceWarning: unclosed database ...` observed during the v3.1 full suite is real diagnostic evidence, but Starlette's warning line can be the garbage-collection site rather than the SQLite allocation site. The repository's `KloneRepository.connection()` explicitly closes its connection in `finally`; it is **not** confirmed to be the leak source.

An **opt-in** `scripts/klone-v34-sqlite-trace.sh` re-runs targeted temporary-database tests with `PYTHONTRACEMALLOC=25` and `ResourceWarning` enabled. It stores device-local output in `~/klone-var/`; it does not touch the currently running app/database, but tests may use their own temporary fixtures. Only after the traceback identifies the real allocation path should code be changed. If the test finishes without warnings, that does not rule out leaks in other suites.

## Remaining roadmap and limitations

- Real process ownership verification requires an independently trusted supervisor identity, not HTTP 200 and not an unsigned health report.
- Future auto-restart requires explicit per-service lifecycle design, OS isolation, scoped storage, service identity, audit, rollback and operator approval. None are granted here.
- Next step: add an authenticated, version-bound health receipt and a current committed test run ledger. This guard intentionally does not claim those are present.
- Preserve PR stack as draft and do not touch `main` or old worktrees until reviewed.
