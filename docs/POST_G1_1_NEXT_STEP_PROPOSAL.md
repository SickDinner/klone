# Post-G1.1 Next Step Proposal

Status: non-canonical architect proposal  
Date: 2026-03-28

This file does not approve a new phase by itself.

Canonical phase control remains in:

- `docs/PROJECT_STATUS.md`
- `docs/HANDOFF_CURRENT.md`
- `docs/ROADMAP.md`

This proposal exists because `Phase G1.1` is complete, the repo is clean apart from the new local commit, and no explicit post-`G1.1` approved substep is currently locked in the canonical docs.

## Verified baseline

As of this proposal:

- `Phase 2B.1` through `Phase 2B.5` are complete
- `Phase 2C.1` through `Phase 2C.5` are complete
- `Phase A1.1` through `Phase A1.8` are complete
- `Phase G1.1` is complete
- `POST /api/ingest/preflight` exists and is verified
- Mission Control intake UI exposes `Preview Manifest` before `Scan Dataset`
- full unittest discovery is green (`75 tests`)
- local HTTP smoke for `/api/ingest/preflight` is green

## Why the next ingest step should stay smaller than a queue

`G1.1` made ingest visible before writes.

The next risk is widening that into infrastructure too quickly:

- resumable jobs
- queues
- manifest persistence with ambiguous lifecycle
- new background-worker semantics

Those are all meaningful additions, but they are not the smallest safe next step.

The smallest safe next step should:

- preserve deterministic local ingest semantics
- remain operator-visible
- avoid background workers
- avoid mutation of ingest meaning
- stay explainability-first

## Recommended next candidate

### Candidate: `G1.2 append-only preflight manifest history`

This is smaller and safer than a resumable queue.

It keeps the ingest operator in a synchronous local workflow and adds only one new capability:

- preserving preflight manifests as append-only preview records for later comparison

That solves a real problem left open by `G1.1`:

- the preview exists only in the moment
- there is no traceable history of what was previewed before the user chose to scan
- there is no stable comparison point between preflight and actual ingest outcomes

## Proposed G1.2 objective

Persist append-only ingest preflight manifest records locally so Mission Control can show recent preview history and compare preview expectations against later ingest execution without introducing async workers or resumable jobs.

## Why this is the smallest useful next step

Compared with the main alternatives:

### Safer than resumable ingest queue work

- no background job lifecycle
- no retry/lease/cancel semantics
- no scheduler or worker shell
- no new operational state machine

### Safer than deeper ingest extraction work

- OCR/transcription widens compute behavior and domain semantics
- manifest history stays close to the current ingest boundary and operator UX

### More useful than pure UI polish alone

- creates an auditable comparison point between preview and scan
- gives the operator a durable record of intended ingest actions
- improves debugging when dedup outcomes differ from expectation

## Proposed G1.2 allowed scope

- add an append-only local manifest-history table or equivalent persistence shell
- persist preflight manifest summaries explicitly as preview records
- expose a bounded read-only recent manifest-history surface for Mission Control
- link a later ingest run to its immediately preceding preview record when applicable
- keep all writes local-first and append-only
- keep the current scan path synchronous

## Proposed G1.2 required outcomes

- each preflight preview can be preserved as a stable historical record
- manifest history remains separate from ingest execution state
- preview history is room-scoped and classification-aware
- an operator can compare preview totals against later ingest totals
- no async worker, queue, retry, or resume semantics are introduced

## Proposed G1.2 acceptance criteria

- compile passes
- focused G1.2 tests pass
- full unittest suite stays green
- preflight history is append-only
- room scope and classification are preserved
- no ingest execution semantics change
- no replay/correction/provenance regressions

## Proposed G1.2 non-goals

- no async queue workers
- no resumable ingest jobs
- no retry scheduler
- no manifest mutation or overwrite
- no OCR/transcription
- no embeddings or semantic inference
- no widening of public `/v1` control-plane routes
- no direct coupling of preview history to memory authority

## Deferred alternatives

### Defer: resumable ingest queue

Reason:

- materially larger operational surface
- requires explicit job lifecycle semantics
- better done after preview history exists

### Defer: preview-to-ingest auto-commit behavior

Reason:

- too easy to blur read-only preview into write authority
- breaks the current explicit operator confirmation posture

### Defer: extraction pipeline expansion

Reason:

- belongs after ingest operability and inspectability are stronger

## Exact supervisor prompt

Use this only if you want to ratify a next approved phase:

```text
Read docs/PROJECT_STATUS.md first, docs/HANDOFF_CURRENT.md second, then docs/ROADMAP.md, docs/DECISIONS.md, docs/AGENT_PLAYBOOK.md, docs/KLONE_AGENT_CONVENTIONS.md, and docs/POST_G1_1_NEXT_STEP_PROPOSAL.md.

Use verified repo evidence only.

Task:
Determine whether the proposed G1.2 append-only preflight manifest history is the next smallest approved ingest substep after G1.1.

Return exactly:
1. current phase
2. what is already canonically complete
3. whether G1.2 should be approved, rejected, or revised
4. next exact smallest safe step
5. who should do it
6. exact handoff prompt
7. what not to do
8. done check
```

## Short recommendation

If the project should keep moving without breaking its own discipline, the next best move is:

1. review this proposal as `KLONE Supervisor` or `KLONE Architect`
2. if accepted, update canonical docs to approve `G1.2`
3. only then implement the smallest append-only manifest-history slice before any queue/resume work
