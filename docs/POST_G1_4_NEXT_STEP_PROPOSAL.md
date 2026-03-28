# Post-G1.4 Next Step Proposal

Status: non-canonical architect proposal  
Date: 2026-03-29

This file does not approve a new phase by itself.

Canonical phase control remains in:

- `docs/PROJECT_STATUS.md`
- `docs/HANDOFF_CURRENT.md`
- `docs/ROADMAP.md`

This proposal exists because `Phase G1.4` is complete, the repo is clean apart from the new local commit, and no explicit post-`G1.4` approved ingest substep is currently locked in the canonical docs.

## Verified baseline

As of this proposal:

- `Phase 2B.1` through `Phase 2B.5` are complete
- `Phase 2C.1` through `Phase 2C.5` are complete
- `Phase A1.1` through `Phase A1.9` are complete
- `Phase G1.1` through `Phase G1.4` are complete
- `POST /api/ingest/preflight` exists and is verified
- `GET /api/ingest/runs/{run_id}/manifest` exists and is verified
- local ingest queue staging, execute, cancel, and interrupted recovery exist and are verified
- Mission Control shows queue depth, inspect, execute/resume, cancel, and manifest handoff controls
- full unittest discovery is green (`89 tests`)
- local HTTP smoke for startup interruption recovery is green

## Why the next ingest step should stay smaller than worker orchestration

`G1.4` made queue recovery visible and resumable without adding a background runtime.

The next risk is widening that into infrastructure too quickly:

- worker daemons
- leases and heartbeat semantics
- automatic retries
- queue scheduling
- distributed execution

Those are all materially larger than the current governed local ingest posture.

The smallest safe next step should:

- preserve deterministic local ingest execution
- improve operator visibility
- remain read-only by default
- reuse existing audit evidence
- avoid inventing a new queue state machine

## Recommended next candidate

### Candidate: `G1.5 bounded ingest queue history seam`

This is smaller and safer than workerization.

It keeps the ingest operator in the current explicit local workflow and adds only one new capability:

- a bounded room-scoped history/detail view for a queue job using already-recorded queue lifecycle audit events

That solves a real problem left open by `G1.4`:

- the operator can see current queue status, but not a durable lifecycle timeline for one job
- interrupted/reused/resumed behavior is visible only indirectly
- queue debugging still depends on broad audit browsing instead of a targeted explainability surface

## Proposed G1.5 objective

Expose a bounded room-scoped ingest queue history seam so Mission Control can inspect the lifecycle of a single queue job using existing queue rows, append-only audit events, and linked ingest-run/manifest references without introducing background workers.

## Why this is the smallest useful next step

Compared with the main alternatives:

### Safer than worker orchestration

- no daemon lifecycle
- no lease expiry semantics
- no concurrent worker ownership
- no scheduler or broker

### Safer than extraction expansion

- OCR/transcription widens compute behavior and domain semantics
- queue history stays close to the current ingest control boundary

### More useful than pure UI polish alone

- creates a direct operator-facing answer to “what happened to this queue job?”
- makes interrupted/reused/resumed behavior explicitly inspectable
- improves debugging without changing ingest authority or execution semantics

## Proposed G1.5 allowed scope

- add one bounded room-scoped queue history/detail read surface
- reuse existing `ingest_queue_jobs`, `audit_events`, and `ingest_run_manifests` evidence
- expose a stable history payload for one queue job
- include linked last-run and manifest visibility when already available
- keep all execution paths unchanged
- keep all queue writes explicit and operator-triggered

## Proposed G1.5 required outcomes

- an operator can inspect one queue job lifecycle without scanning the full room audit feed
- interrupted, reused, completed, failed, and cancelled transitions are visible when present
- linked ingest run and manifest references are visible when already present
- room scope and classification are preserved
- no new queue states, workers, or auto-execution behavior are introduced

## Proposed G1.5 acceptance criteria

- compile passes
- focused G1.5 tests pass
- full unittest suite stays green
- queue history remains read-only
- room scope is preserved
- queue execution semantics stay unchanged
- startup recovery semantics stay unchanged
- no replay/correction/provenance regressions

## Proposed G1.5 non-goals

- no worker daemon
- no retry scheduler
- no automatic resume
- no queue mutation beyond existing stage/execute/cancel paths
- no OCR/transcription
- no embeddings or semantic inference
- no widening of public `/v1` control-plane routes
- no direct coupling of queue history to memory authority

## Deferred alternatives

### Defer: background worker or lease model

Reason:

- materially larger operational surface
- requires explicit ownership and recovery semantics
- not needed yet for local-first operator-controlled ingest

### Defer: automatic retry or startup auto-execute

Reason:

- breaks the current explicit operator control posture
- makes interruption recovery harder to debug

### Defer: extraction pipeline expansion

Reason:

- belongs after ingest explainability and operability are stronger

## Exact supervisor prompt

Use this only if you want to ratify a next approved phase:

```text
Read docs/PROJECT_STATUS.md first, docs/HANDOFF_CURRENT.md second, then docs/ROADMAP.md, docs/DECISIONS.md, docs/AGENT_PLAYBOOK.md, docs/KLONE_AGENT_CONVENTIONS.md, and docs/POST_G1_4_NEXT_STEP_PROPOSAL.md.

Use verified repo evidence only.

Task:
Determine whether the proposed G1.5 bounded ingest queue history seam is the next smallest approved ingest substep after G1.4.

Return exactly:
1. current phase
2. what is already canonically complete
3. whether G1.5 should be approved, rejected, or revised
4. next exact smallest safe step
5. who should do it
6. exact handoff prompt
7. what not to do
8. done check
```

## Short recommendation

If the project should keep moving without breaking its own discipline, the next best move is:

1. review this proposal as `KLONE Supervisor` or `KLONE Architect`
2. if accepted, update canonical docs to approve `G1.5`
3. only then implement the smallest queue-history explainability slice before any workerization
