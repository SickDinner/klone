# Post-A1.3 Next Step Proposal

Status: non-canonical architect proposal  
Date: 2026-03-28

This file does not approve a new phase by itself.

Canonical phase control remains in:

- `docs/PROJECT_STATUS.md`
- `docs/HANDOFF_CURRENT.md`
- `docs/ROADMAP.md`

This proposal exists because Phase A1.3 is already complete, the repo is clean, and no explicit next approved control-plane substep is currently locked in the canonical docs.

## Verified baseline

As of this proposal:

- `Phase 2B.1` through `Phase 2B.5` are complete
- `Phase 2C.1` through `Phase 2C.5` are complete
- `Phase A1.1` through `Phase A1.3` are complete
- `main` is in sync with `origin/main`
- full unittest discovery is green (`50 tests`)
- public `/v1` surface remains a single read-only `GET /v1/capabilities` route

## Why no runtime widening should happen yet

The canonical docs explicitly say that after `A1.3`, the next step must be selected from verified repo evidence only.

That means:

- do not add a new `/v1` route just because the contract shells exist
- do not widen query semantics
- do not touch mutation surfaces
- do not let the control plane drift into a broad public API without an approved narrow seam

## Recommended next candidate

### Candidate: `A1.4 local object shell projection via existing governed routes`

This is the smallest plausible next control-plane seam because it stays within the existing design language:

- read-only only
- uses existing governed routes
- no new `/v1` object route yet
- no write surface
- no semantic retrieval widening

It is also safer than a query-shell or change-shell expansion:

- `query-shell` risks widening retrieval semantics too early
- `change-shell` risks colliding with correction/replay/audit invariants
- `object-shell` can stay purely descriptive and deterministic

## Proposed A1.4 objective

Project a stable read-only object shell over already existing governed resources without introducing a new public `/v1` object endpoint.

## Proposed A1.4 allowed scope

- add a deterministic object-shell record model if needed
- map existing governed rows into object-shell projections
- surface capability visibility through `GET /v1/capabilities`
- reuse existing `/api/datasets`, `/api/assets`, `/api/memory/events`, and `/api/memory/episodes` read routes where appropriate
- keep all behavior additive and read-only

## Proposed A1.4 required outcomes

- stable public object-shell identity rules are explicit
- object-shell projection is deterministic over existing governed rows
- `/v1/capabilities` shows which existing routes currently back object-shell visibility
- no new `/v1` object route is added
- room scope and classification remain explicit
- no mutation authority is introduced

## Proposed A1.4 acceptance criteria

- compile passes
- focused A1.4 tests pass
- full unittest suite stays green
- `/v1` route surface remains unchanged
- capability exposure is deterministic
- no replay/correction/provenance regressions

## Proposed A1.4 non-goals

- no `/v1/objects/get`
- no `/v1/objects/set`
- no semantic search
- no fuzzy matching
- no embeddings
- no write surfaces
- no direct blob upload surface
- no change feed

## Deferred alternatives

### Defer: query-shell runtime expansion

Reason:

- higher risk of semantic widening
- more likely to create overlap with existing memory retrieval surfaces

### Defer: change-shell runtime expansion

Reason:

- too close to correction/replay/audit invariants
- easier to mis-signal as public mutation support

### Defer: blob route addition

Reason:

- A1.3 deliberately proved blob metadata over existing asset routes first
- adding `/v1/blobs/{blob_id}/meta` now would widen the public control plane without clear need

## Exact supervisor prompt

Use this only if you want to ratify a next approved phase:

```text
Read docs/PROJECT_STATUS.md first, docs/HANDOFF_CURRENT.md second, then docs/ROADMAP.md, docs/DECISIONS.md, docs/AGENT_PLAYBOOK.md, docs/KLONE_AGENT_CONVENTIONS.md, and docs/POST_A1_3_NEXT_STEP_PROPOSAL.md.

Use verified repo evidence only.

Task:
Determine whether the proposed A1.4 local object shell projection is the next smallest approved control-plane substep.

Return exactly:
1. current phase
2. what is already canonically complete
3. whether A1.4 should be approved, rejected, or revised
4. next exact smallest safe step
5. who should do it
6. exact handoff prompt
7. what not to do
8. done check
```

## Short recommendation

If the project should keep moving without breaking its own discipline, the next best move is:

1. review this proposal as `KLONE Supervisor` or `KLONE Architect`
2. if accepted, update canonical docs to approve `A1.4`
3. only then implement the smallest object-shell projection slice
