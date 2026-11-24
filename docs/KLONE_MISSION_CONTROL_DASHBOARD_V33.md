# KLONE v3.3 — Mission Control Dashboard (LAB, localhost-only)

Branch stacked on v3.2 commit `96c9d50f114e4fef6f1bba2b599400df5ace2ad3`.

## Context / observed device state (user-provided, 2026-11-24)

- Port `8000` has an existing Uvicorn process from `~/klone-next` and reports `status: ok`.
- Ports `8001`, `8010`, `8011`, `8012`, `8020` did not listen at the time of the user's checks.
- Two old `klone_control.py` programs default to port 8000 with `owner_debug=True`; DO NOT start these to restore Mission Control. They manage the API and may create a second instance with a separate DB configuration.
- The old `mission_control.py`, `klone_rescue.py` and `klone_chat.py` entry points were not found in the bounded search. Absence in that scope does not prove deletion.

## What this PR does

`klone.mission_control_dashboard_v33` provides a **separately opt-in**, **foreground-only** HTTP page at **`http://127.0.0.1:8011/`**, binding to the numeric IPv4 loopback address only. There is no default auto-start and no dependency on legacy control programs. It reuses the existing v3.2 health observer without modifying the observer, current KLONE API, data directories or SQLite database.

- Reads only fixed v3.2 endpoints: main 8000, next 8001, status 8010, chat UI 8012, recovery 8020. **Self-port 8011 is deliberately excluded** from the probes to avoid circular requests and a deadlock in the single-threaded HTTP server.
- Shows 5 service states, timing and the untrusted report's SHA-256. An HTTP 200 or `status: ok` is **not a verified process identity, security attestation, application readiness or owner grant**.
- The page shows no server response body, database paths, bearer tokens, cookies or application content. It does not send remote network requests, invoke a model, start other services or persist anything.
- Rejects nonmatching `Host`, foreign `Origin`, cross-site fetch metadata and all paths except `/`; HTML-escapes presentation, includes restrictive headers (CSP, no-store, nosniff, frame denial). No active JavaScript or background refresh; user chooses when to reload.
- **This is NOT an authenticated production dashboard.** Other apps on the same Android device that can access loopback may reach the page. Keep it local; do not port-forward, tunnel or advertise it on LAN.
- Displays 8011 as "this page" but does not include it in the 5-service report digest. Running the **separate** full v3.2 loopback probe after starting the page should change its 8011 result to `reachable_unverified`, which is still *not* agent health.

## One-time Android startup (only after testing the exact commit)

From a **separate Termux session**:

```sh
cd ~/klone-v33-dashboard
PYTHONPATH="$PWD/src" "$HOME/klone-next/.venv/bin/python" \
  -m klone.mission_control_dashboard_v33 --serve-local
```

Open `http://127.0.0.1:8011/` on the same phone. Stop with Ctrl+C. This does not change the already running port 8000. Port 8011 busy -> clean error and no attempt to terminate another process.

## Tests

```sh
PYTHONPATH=src python -m unittest discover -s tests -p 'test_mission_control_dashboard_v33.py' -q
PYTHONPATH=src python -m unittest discover -s tests -p 'test_*.py' -q
```

The new cases cover no default launch, loopback host/origin guards, actual local HTTP handler, 503 fail-closed error, no private output, v3.2 SHA-256 checking, precise 5/5 endpoint coverage, security headers, false authority escalation and no self-probe.

Use `bash scripts/klone-v33-termux-verify.sh <exact-commit-40hex>` from the pinned checkout on Android, which also enables the existing system `cryptography` for the test process only; no library installation or service startup is performed.

## Follow-up work (not claimed implemented)

- Audit process identity using OS-level service identity + signed health receipts; no app-level self-report as identity proof.
- Durable service management with unique locks, explicit DB isolation and owner opt-in, not hidden process restarts.
- Investigate resource warnings from SQLite with `PYTHONTRACEMALLOC` before fixing ownership or connection paths.
- Add a verified snapshot/attestation backend before exposing data beyond local, trusted development.
- Integrate a sealed/restricted-room review UI only behind an authenticated, audited room-scoped service (out of scope).
