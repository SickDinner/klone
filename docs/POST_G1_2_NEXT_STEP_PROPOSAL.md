# Post-G1.2 Next Step Proposal

Status: non-canonical architect proposal  
Date: 2026-03-28

This file does not approve a new phase by itself.

Canonical phase control remains in:

- `docs/PROJECT_STATUS.md`
- `docs/HANDOFF_CURRENT.md`
- `docs/ROADMAP.md`

This proposal exists because `Phase G1.2` is complete and no explicit post-`G1.2` approved substep is currently locked in the canonical docs.

## Verified baseline

As of this proposal:

- `Phase 2B.1` through `Phase 2B.5` are complete
- `Phase 2C.1` through `Phase 2C.5` are complete
- `Phase A1.1` through `Phase A1.8` are complete
- `Phase G1.1` and `Phase G1.2` are complete
- `POST /api/ingest/preflight` exists and is verified
- `GET /api/ingest/runs/{run_id}/manifest` exists and is verified
- Mission Control already supports preview-before-scan and manifest inspection for completed runs
- full unittest discovery is green in current repo reality

## Why the next ingest step should still stay local and narrow

`G1.1` made ingest visible before writes.

`G1.2` made completed ingest runs inspectable after writes.

The next remaining operator pain is not missing metadata anymore. It is control over long or interrupted scans.

That suggests queue/resume work is the right neighborhood, but the next move should still stay smaller than:

- distributed workers
- external brokers
- automatic retries
- startup-time job resurrection
- full scheduling orchestration

The safest next step is a local queue shell, not a full job system.

## Recommended next candidate

### Candidate: `G1.3 local resumable ingest queue shell`

This is the smallest next step that matches the repo's current ingest direction.

It should introduce explicit local ingest session state and bounded resume behavior while keeping everything:

- local-first
- single-process
- operator-driven
- deterministic
- auditable

## Proposed G1.3 objective

Add a local resumable ingest queue shell so Mission Control can stage, start, interrupt, and explicitly resume one governed ingest session at a time without introducing distributed workers or changing ingest semantics.

## Why this is the smallest useful next step

Compared with the main alternatives:

### Better than jumping straight to async worker orchestration

- smaller operational surface
- easier to debug locally
- no broker or scheduler dependency
- fewer hidden states

### Better than skipping directly to OCR/transcription

- operator control over ingest execution is still the more foundational problem
- extraction expansion belongs after ingest execution control is stronger

### Better than pure UI polish

- solves a real control-gap in the ingest spine
- creates the minimum necessary lifecycle language for longer scans

## Proposed G1.3 allowed scope

- add a local ingest session record or queue record model
- introduce explicit queued / running / interrupted / completed style status vocabulary for ingest sessions
- add the smallest operator-triggered resume path for an interrupted local ingest session
- keep execution in-process and local-first
- expose bounded session visibility in Mission Control
- preserve preflight and manifest-history behavior as-is

## Proposed G1.3 required outcomes

- one ingest session can be staged and resumed explicitly
- queue/session state is visible and auditable
- the user can tell whether a session is queued, running, interrupted, or completed
- resumed work does not duplicate already indexed assets inside the same session boundary
- current scan semantics remain deterministic

## Proposed G1.3 acceptance criteria

- compile passes
- focused G1.3 tests pass
- regression slice for G1.1 and G1.2 passes
- full unittest suite stays green
- no distributed queue or external broker appears
- no ingest result drift appears between uninterrupted and resumed local runs
- room scope, classification, dedup, and audit behavior remain intact

## Proposed G1.3 non-goals

- no distributed workers
- no broker
- no Celery, Kafka, Redis, or equivalent expansion
- no multi-host execution
- no automatic retry scheduler
- no startup-time auto-resume
- no OCR/transcription
- no semantic search or embeddings
- no change to memory authority or evidence semantics

## Deferred alternatives

### Defer: distributed ingest queue

Reason:

- too large for the current repo posture
- not justified while the app is still local-first and single-process

### Defer: full extraction pipeline orchestration

Reason:

- extraction work is downstream of ingest execution control
- easier to reason about after queue/session vocabulary exists

### Defer: manifest-history widening into full archival

Reason:

- `G1.2` is already sufficient for bounded run inspection
- broader archival policy should wait until queue/session semantics settle

## Exact supervisor prompt

Use this only if you want to ratify a next approved phase:

```text
Read docs/PROJECT_STATUS.md first, docs/HANDOFF_CURRENT.md second, then docs/ROADMAP.md, docs/DECISIONS.md, docs/AGENT_PLAYBOOK.md, docs/KLONE_AGENT_CONVENTIONS.md, and docs/POST_G1_2_NEXT_STEP_PROPOSAL.md.

Use verified repo evidence only.

Task:
Determine whether the proposed G1.3 local resumable ingest queue shell is the next smallest approved ingest substep after G1.2.

Return exactly:
1. current phase
2. what is already canonically complete
3. whether G1.3 should be approved, rejected, or revised
4. next exact smallest safe step
5. who should do it
6. exact handoff prompt
7. what not to do
8. done check
```

## Short recommendation

If the project should keep moving without breaking its own discipline, the next best move is:

1. review this proposal as `KLONE Supervisor` or `KLONE Architect`
2. if accepted, update canonical docs to approve `G1.3`
3. only then implement the smallest local resumable ingest queue shell without jumping to distributed job infrastructure
