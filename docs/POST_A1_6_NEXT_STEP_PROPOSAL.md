# Post-A1.6 Next Step Proposal

Status: non-canonical architect proposal  
Date: 2026-03-28

This file does not approve a new phase by itself.

Canonical phase control remains in:

- `docs/PROJECT_STATUS.md`
- `docs/HANDOFF_CURRENT.md`
- `docs/ROADMAP.md`

This proposal exists because `Phase A1.6` is complete, the repo is clean, and no explicit next approved control-plane substep is currently locked in the canonical docs.

## Verified baseline

As of this proposal:

- `Phase 2B.1` through `Phase 2B.5` are complete
- `Phase 2C.1` through `Phase 2C.5` are complete
- `Phase A1.1` through `Phase A1.6` are complete
- `main` is in sync with `origin/main`
- full unittest discovery is green (`64 tests`)
- local HTTP smoke is green for `POST /v1/rooms/{room_id}/query`
- public `/v1` surface currently contains exactly:
  - `GET /v1/capabilities`
  - `POST /v1/rooms/{room_id}/objects/get`
  - `POST /v1/rooms/{room_id}/query`

## Why runtime widening should still stay narrow

The canonical docs explicitly say that after `A1.6`, the next step must be approved before widening the control plane again.

That means:

- do not add `/v1/changes`
- do not add `/v1/objects/set`
- do not add blob upload or blob metadata write surfaces
- do not widen query kinds beyond `memory_events` and `memory_episodes`
- do not add semantic search, embeddings, fuzzy matching, or query-time synthesis

The safest next move should deepen explainability, not widen intelligence or mutation authority.

## Recommended next candidate

### Candidate: `A1.7 provenance shell capability mapping via existing governed routes`

This candidate is intentionally smaller than a new public provenance route.

It stays at the control-plane visibility layer:

- read-only only
- no new `/v1` runtime route yet
- no mutation authority
- no semantic widening
- no duplicate provenance logic

It is also especially aligned with KLONE's current doctrine:

- `D-001 Evidence immutability`
- `D-002 Room scoping`
- `D-006 Read-only public memory API`
- `D-007 Provenance first`

## Proposed A1.7 objective

Expose deterministic provenance-shell capability mapping through `GET /v1/capabilities` using the already existing governed provenance detail routes:

- `/api/memory/events/{event_id}/provenance`
- `/api/memory/episodes/{episode_id}/provenance`

without adding a new public `/v1` provenance endpoint in this phase.

## Proposed A1.7 allowed scope

- add a provenance-shell contract record if needed
- expose provenance capability visibility through `GET /v1/capabilities`
- map existing governed provenance detail routes as backing surfaces
- keep all behavior additive and read-only
- reuse request context and append-only control-plane audit chaining on `GET /v1/capabilities`

## Proposed A1.7 required outcomes

- stable provenance-shell identity is explicit in the public control plane
- `/v1/capabilities` shows which existing routes back provenance visibility
- provenance-shell visibility remains declarative and capability-only in this phase
- no new `/v1` provenance route is added
- room scope remains explicit
- source lineage remains the center of the seam

## Proposed A1.7 acceptance criteria

- compile passes
- focused A1.7 tests pass
- full unittest discovery stays green
- `/v1` route surface remains unchanged
- provenance capability exposure is deterministic
- no replay/correction/provenance regressions
- no new write or semantic query behavior exists after the change

## Proposed A1.7 non-goals

- no `/v1/rooms/{room_id}/provenance/get`
- no `/v1/changes`
- no `/v1/objects/set`
- no blob upload surface
- no semantic search
- no fuzzy matching
- no embeddings
- no query-time synthesis
- no mutation surfaces

## Deferred alternatives

### Defer: public provenance route

Reason:

- larger than necessary for the next seam
- should only happen after provenance capability visibility is explicit and tested first

### Defer: change-shell runtime expansion

Reason:

- too close to correction/replay/audit invariants
- easier to mis-signal as public mutation support

### Defer: object write surfaces

Reason:

- directly widens authority
- not justified by current roadmap discipline

### Defer: broader query widening

Reason:

- current query seam is intentionally narrow
- widening query kinds too early increases semantic drift risk

## Exact supervisor prompt

Use this only if you want to ratify a next approved phase:

```text
Read docs/PROJECT_STATUS.md first, docs/HANDOFF_CURRENT.md second, then docs/ROADMAP.md, docs/DECISIONS.md, docs/AGENT_PLAYBOOK.md, docs/KLONE_AGENT_CONVENTIONS.md, and docs/POST_A1_6_NEXT_STEP_PROPOSAL.md.

Use verified repo evidence only.

Task:
Determine whether the proposed A1.7 provenance shell capability mapping is the next smallest approved control-plane substep after completed Phase A1.6.

Return exactly:
1. current phase
2. what is already canonically complete
3. whether A1.7 should be approved, rejected, or revised
4. next exact smallest safe step
5. who should do it
6. exact handoff prompt
7. what not to do
8. done check
```

## Short recommendation

If the project should keep moving without breaking its own discipline, the next best move is:

1. review this proposal as `KLONE Supervisor` or `KLONE Architect`
2. if accepted, update canonical docs to approve `A1.7`
3. only then implement the smallest provenance-shell capability-mapping slice
