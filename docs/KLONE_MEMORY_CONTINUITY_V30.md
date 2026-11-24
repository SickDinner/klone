# KLONE v3.0 – Memory Continuity & System Review Pulse (LAB ONLY)

Date: 2026-11-24. Base: `feat/proof-carrying-cognition-v29-lab-20261124`
(`1845d2b6bbc8558d2739ddb90379f4f158978698`). No changes to the
existing memory database schema, ACL, security principal or production API.

## Why this layer exists

Memory Core **already** records `active`, `rejected`, `superseded`,
`corrected_at`, `correction_reason`, `corrected_by_role` and
`superseded_by_id`. Do not create a second, competing memory database.
The new read-only layer compares two public-room *metadata snapshots* and
flags impossible or suspicious transitions. It can be used by a trusted
reviewer to decide which anomalies need investigation, never as permission
for write/publish/execute.

- A corrected/rejected entry cannot become `active` without a flagged drift.
- Previously corrected reason, time, role and replacement cannot be rewritten.
- An existing event cannot disappear without a flagged drift.
- Source timing, event identity, room and classification are immutable across
  the two reported snapshots.
- Replacement must exist in the same supplied complete snapshot, must have
  been recorded by the source's correction time, and cannot create a cycle.
- Input snapshots and report are bounded to 512 records and deterministic.
- `project_public_memory_events()` projects only the existing `MemoryService`
  result metadata and explicitly refuses non-public rooms. Even field names
  such as `evidence_text` are never copied to the new data objects.
- Input record correction flags, when present, must agree with the status.
- Current snapshot reports cannot be trusted for historical time-travel; no
  bitemporal reconstruction from a mutable latest-state table is claimed.

**Critical limitation:** A list obtained with `limit`/`offset` is **not** a
complete snapshot; the source must first enforce a consistent transaction,
source authorization, complete coverage, stable boundary, and independent
anchor. Comparing two attacker-controlled pages or a changed partial sample
is **not** an integrity guarantee. Same-DB metadata SHA-256 cannot prove
provenance or detect every malicious rewrite. Current code intentionally
sets `full_database_coverage_verified=false`, `source_snapshot_authenticated=false`,
`historical_integrity_externally_anchored=false` and `deployment_approval=false`.
Changing raw content while preserving metadata is NOT detected by this lab.

## System review pulse (12 domains)

`build_system_review_pulse()` re-runs the memory check and composes it with
KLONE's existing `summarize_acceptance()` contract for all twelve domains.
It lists `failed`/`pending`/`unverified`/`not_applicable` as unresolved and
also always identifies absence of external provenance, isolated runtime
identity, independent audit anchor and deployment approval. Even if a caller
reports all domains `passed`, **production_readiness_verified is false**.

The pulse does not contact services or claim to have tested actual runtime
health. Its states are caller-declared, not authenticated. The report is a
Mission Control *review input*, not a live status probe or capability token.

## Novel cross-module integration path (implementation backlog)

1. **Memory Core:** immutable history of correction events stored separately
   from the current rows, with verified independent checkpoint publication.
   Supply a consistent, complete snapshot **through an authorized room-scoped
   facade**; avoid exposing direct database selectors on web APIs.
2. **Hypervisor:** issue short-lived, versioned, context-bound capability
   references from an isolated service principal. Deny if room, purpose,
   proof version, expiry, quota or audit transaction changes. Never treat the
   v3.0 pulse or v2.9's policy preview as a grant.
3. **Council72:** append provenance-linked memory-update *proposals* to
   replayable sessions. Preserve dissent; never let 72 dependent votes be
   counted as independent evidence; uncertain and superseded evidence stays
   visible for review without being reactivated.
4. **Research:** attach independently obtained source identifiers and
   correction tombstones to claims, with an auditable redaction policy and
   verifier for evidence packet origin.
5. **Cognition:** calibrate confidence on genuinely held-out source groups;
   require improvement over baselines before any new scheduling policy.
6. **Genomics:** separate per-person sensitive data with dedicated OS service
   identity and explicit exports; block this public-room lab from reading it.
7. **Media:** add content-addressed local assets with attribution, license and
   consent metadata; handle protected media inside proper rooms.
8. **Simulation:** immutable fork identifiers and no promotion of simulated
   outcomes to real-world evidence without an independently measured event.
9. **Android / Termux:** isolate processes where the OS permits; benchmark
   memory-pressure, thermal trends, battery drain, restarts and crash recovery.
   Distinguish process CPU snapshots from per-agent energy consumption.
10. **CI / evidence:** add source-provenance attestations and stress tests for
    history pruning, clock skew, conflicting correction chains and concurrent
    snapshot reads. Reuse existing v2.5 signed audit work where appropriate.
11. **Mission Control:** expose a compact `known / unverified / blocked`
    status for all 12 domains with exact commit, build, environment and source
    of claim; mark synthetic fixtures prominently.
12. **Deployment:** manual review and explicit owner confirmation after
    isolated-principal and key-storage checks. No automatic promotion from
    green unit tests, Council72 votes or an unsigned local report.

## Test invocation

```
PYTHONPATH=src python -m unittest discover -s tests -p 'test_memory_continuity_v30.py' -v
PYTHONPATH=src python -m unittest discover -s tests -p 'test_system_readiness_v30.py' -v
PYTHONPATH=src python -m unittest discover -s tests -p 'test_*.py'
```

The new tests use only Python's standard library. Python >=3.11.
This PR must remain draft until cross-platform CI and Android/Termux run
against the *exact new commit*. Existing PRs and `main` are untouched.
