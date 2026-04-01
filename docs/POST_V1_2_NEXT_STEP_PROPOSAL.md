# Post-V1.2 Next Step Proposal

Status: non-canonical architect proposal  
Date: 2026-04-01

This file does not approve a new phase by itself.

Canonical phase control remains in:

- `docs/PROJECT_STATUS.md`
- `docs/HANDOFF_CURRENT.md`
- `docs/ROADMAP.md`

This proposal exists because `Phase V1.2` is complete, the repo is clean apart from local docs updates, and no explicit post-`V1.2` approved art-lab substep is currently locked in the canonical docs.

## Verified baseline

As of this proposal:

- `Phase 2B.1` through `Phase 2B.5` are complete
- `Phase 2C.1` through `Phase 2C.5` are complete
- `Phase A1.1` through `Phase A1.9` are complete
- `Phase G1.1` through `Phase G1.5` are complete
- `Phase V1.1` and `Phase V1.2` are complete
- `GET /api/art/assets/{asset_id}/metrics` exists and is verified
- `GET /api/art/assets/compare` exists and is verified
- Mission Control already exposes a single-asset `Art Metrics` panel for supported image assets
- Mission Control does not yet expose an explicit bounded multi-asset comparison workflow over the completed `V1.2` seam
- full unittest discovery is green locally (`101 tests`)

## Why the next art-lab step should stay smaller than OCR or profiling expansion

`V1.2` closed the backend comparison seam safely:

- room-scoped
- explicit bounded asset set
- deterministic formal metrics only
- no learned features
- no writeback

The next risk is jumping from that explainable comparison seam into a larger interpretation layer too early:

- OCR or text extraction
- embeddings or semantic similarity
- clustering or profiling
- personality-style interpretation
- public `/v1` expansion

Those all widen either domain authority, API surface, or interpretive risk.

The smallest safe next step should:

- stay read-only
- reuse the already-completed `V1.2` backend contract
- add operator visibility rather than new inference
- preserve explicit room scope and bounded asset selection
- avoid new persisted derived state

## Recommended next candidate

### Candidate: `V1.3 Mission Control bounded art comparison panel`

This is smaller and safer than any new analysis surface.

It keeps the art-lab grounded in the already-completed `V1.1` and `V1.2` semantics and adds only one new capability:

- an operator-facing Mission Control workflow for selecting a bounded same-room set of governed image assets and inspecting the existing comparison payload directly

That solves the real gap left open after `V1.2`:

- the compare route exists, but it is still an API-only seam
- Mission Control shows only single-asset metrics today
- operators cannot inspect side-by-side metric drift without manually calling the route outside the UI
- the art-lab remains more capable in backend reality than in the visible cockpit

## Proposed V1.3 objective

Expose the existing bounded room-scoped art comparison seam inside Mission Control so operators can compare an explicit small set of governed image assets using the already-approved deterministic metric set without adding new metrics, routes, or interpretation layers.

## Why this is the smallest useful next step

Compared with the main alternatives:

### Safer than OCR or text extraction

- no extraction pipeline expansion
- no new document or text authority
- no additional compute semantics

### Safer than embeddings or semantic similarity

- no learned representation layer
- no fuzzy retrieval semantics
- no hidden ranking behavior

### Safer than clustering or profiling

- no automatic grouping claims
- no inferred style identity
- no clinical or psychological drift

### More useful than docs-only polish

- exposes a completed backend seam to the actual operator workflow
- improves explainability and usability immediately
- does not require inventing a new phase family or widening the public API

## Proposed V1.3 allowed scope

- add one Mission Control compare panel or compare workflow using the existing `/api/art/assets/compare` route only
- allow explicit bounded selection of existing same-room image assets only
- reuse the existing deterministic `V1.2` comparison payload exactly as-is
- show ordered compared assets, side-by-side metric values, and existing first-to-last deltas only
- surface current validation and rejection behavior clearly in the UI
- add focused frontend or route-integration verification only as needed to prove the compare workflow works end-to-end

## Proposed V1.3 required outcomes

- an operator can select a bounded same-room image asset set from Mission Control and inspect the existing comparison payload
- the compare workflow remains read-only
- room scope is preserved throughout the workflow
- non-image and invalid bounded-selection errors remain explicit
- `V1.1` single-asset metrics behavior stays unchanged
- `V1.2` comparison semantics stay unchanged

## Proposed V1.3 acceptance criteria

- compile passes
- focused `V1.1` tests pass
- focused `V1.2` tests pass
- full unittest discovery stays green
- no new API routes are added
- no new art metrics are added
- no persistence or writeback is introduced
- no `/v1` art surface is introduced

## Proposed V1.3 non-goals

- no OCR
- no embeddings
- no semantic similarity
- no clustering
- no profiling dashboards
- no personality or clinical inference
- no batch writeback
- no saved comparison sessions
- no public `/v1` art comparison route
- no cross-room comparison

## Deferred alternatives

### Defer: OCR or text-bearing image interpretation

Reason:

- widens the art-lab into extraction semantics rather than keeping it as a formal metrics lab

### Defer: embeddings or semantic image similarity

Reason:

- introduces a harder-to-explain learned layer before the visible deterministic comparison workflow is even surfaced

### Defer: clustering or longitudinal profile generation

Reason:

- creates inferred grouping authority too early
- risks turning the art-lab into a profiling system instead of a governed measurement system

### Defer: public `/v1` art-lab expansion

Reason:

- the compare seam should first be visible and validated inside Mission Control before widening the external contract surface

## Exact supervisor prompt

Use this only if you want to ratify a next approved phase:

```text
Read docs/PROJECT_STATUS.md first, docs/HANDOFF_CURRENT.md second, then docs/ROADMAP.md, docs/DECISIONS.md, docs/AGENT_PLAYBOOK.md, docs/KLONE_AGENT_CONVENTIONS.md, README.md, src/klone/static/index.html, src/klone/static/app.js, src/klone/api.py, src/klone/art.py, and docs/POST_V1_2_NEXT_STEP_PROPOSAL.md.

Use verified repo evidence only.

Task:
Determine whether the proposed V1.3 Mission Control bounded art comparison panel is the next smallest approved art-lab substep after V1.2.

Return exactly:
1. current phase
2. what is already canonically complete
3. whether V1.3 should be approved, rejected, or revised
4. next exact smallest safe step
5. who should do it
6. exact handoff prompt
7. what not to do
8. done check
```

## Short recommendation

If the project should keep moving without breaking its own discipline, the next best move is:

1. review this proposal as `KLONE Supervisor` or `KLONE Architect`
2. if accepted, update canonical docs to approve `V1.3`
3. only then implement the smallest UI-visible compare workflow before any OCR, embeddings, clustering, profiling, or public `/v1` art expansion
