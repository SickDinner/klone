# Post-V1.1 Next Step Proposal

Status: non-canonical architect proposal  
Date: 2026-04-01

This file does not approve a new phase by itself.

Canonical phase control remains in:

- `docs/PROJECT_STATUS.md`
- `docs/HANDOFF_CURRENT.md`
- `docs/ROADMAP.md`

This proposal exists because `Phase V1.1` is complete, the repo is clean apart from the new local commit, and no explicit post-`V1.1` approved art-lab substep is currently locked in the canonical docs.

## Verified baseline

As of this proposal:

- `Phase 2B.1` through `Phase 2B.5` are complete
- `Phase 2C.1` through `Phase 2C.5` are complete
- `Phase A1.1` through `Phase A1.9` are complete
- `Phase G1.1` through `Phase G1.5` are complete
- `Phase V1.1` is complete
- `GET /api/art/assets/{asset_id}/metrics` exists and is verified
- art metrics remain deterministic, single-asset, read-only, and room-scoped
- Mission Control exposes an Art Metrics panel for supported image assets
- `/v1/capabilities` exposes art-lab capability visibility
- full unittest discovery is green (`97 tests`)

## Why the next art-lab step should stay smaller than profiling expansion

`V1.1` proved that governed image assets can support deterministic formal metrics without widening into inference-heavy behavior.

The next risk is jumping too quickly into a broader analysis layer:

- room-wide profiling
- implicit clustering
- personality-style interpretation
- OCR or text extraction drift
- embeddings or semantic similarity

Those all widen the art-lab away from its current formal-measurement posture.

The smallest safe next step should:

- stay read-only
- remain asset-backed
- reuse existing deterministic single-asset metrics
- make comparisons inspectable without inventing a new intelligence layer
- avoid storing new derived authority unless clearly justified

## Recommended next candidate

### Candidate: `V1.2 bounded batch art metrics and longitudinal comparison seam`

This is smaller and safer than any profiling or clustering expansion.

It keeps the art-lab grounded in already-approved formal metrics and adds only one new capability:

- a bounded room-scoped comparison surface across multiple existing image assets using the same deterministic metric set already exposed in `V1.1`

That solves the real gap left open by `V1.1`:

- operators can inspect one image asset at a time, but not compare a small set of related assets directly
- longitudinal visual drift remains implicit and manual
- Mission Control cannot yet answer simple questions like “how did these drawings differ in brightness, balance, or symmetry over time?” without many separate reads

## Proposed V1.2 objective

Expose a bounded room-scoped batch comparison seam for existing governed image assets so Mission Control can inspect deterministic formal metric deltas and simple longitudinal ordering without adding OCR, embeddings, clustering, or personality inference.

## Why this is the smallest useful next step

Compared with the main alternatives:

### Safer than embeddings or semantic similarity

- no learned vector space
- no fuzzy retrieval semantics
- no hidden cross-asset inference layer

### Safer than clustering or profiling

- no automatic grouping claims
- no emergent “style identity” logic
- no clinical or psychological overreach

### More useful than UI polish alone

- gives a direct operator-facing answer to “how do these image assets differ formally?”
- makes time-adjacent or hand-picked asset comparisons explicit
- improves the lab’s explainability without changing ingest, memory, or control-plane authority

## Proposed V1.2 allowed scope

- add one bounded room-scoped read-only comparison surface for existing image assets only
- reuse the existing formal metrics set from `V1.1`
- allow a bounded asset set or bounded time-ordered slice for comparison
- expose deterministic metric deltas, side-by-side values, and simple ordering metadata only
- reuse existing governed asset reads and room permissions
- keep all art-lab behavior additive and read-only

## Proposed V1.2 required outcomes

- an operator can compare a bounded set of image assets without calling the single-asset route repeatedly by hand
- longitudinal ordering is visible when asset timestamps already exist in governed metadata
- formal metric differences remain transparent and source-linked to the compared assets
- room scope and output-guard behavior are preserved
- no new derived personality, sentiment, or clinical interpretation is introduced

## Proposed V1.2 acceptance criteria

- compile passes
- focused V1.2 tests pass
- full unittest suite stays green
- comparison remains read-only
- compared assets remain room-scoped
- V1.1 single-asset metrics behavior stays unchanged
- no ingest, replay, correction, or evidence_text regressions

## Proposed V1.2 non-goals

- no OCR
- no embeddings
- no semantic similarity search
- no automatic clustering
- no batch writeback or persisted profile rows
- no personality or clinical inference
- no widening into genomics, memory, or public `/v1` surfaces

## Deferred alternatives

### Defer: embeddings or semantic image similarity

Reason:

- would widen retrieval semantics beyond the current formal-measurement lab
- harder to explain and verify than deterministic metric comparisons

### Defer: automatic style clustering

Reason:

- introduces inferred grouping authority too early
- risks silently becoming a profile system instead of a measurement system

### Defer: OCR or text-bearing image interpretation

Reason:

- belongs to a later extraction pipeline, not the current art-lab seam

### Defer: room-wide profiling dashboards

Reason:

- larger UI and storage surface than needed for the next bounded art-lab step
- should follow only after the comparison seam is accepted and verified

## Exact supervisor prompt

Use this only if you want to ratify a next approved phase:

```text
Read docs/PROJECT_STATUS.md first, docs/HANDOFF_CURRENT.md second, then docs/ROADMAP.md, docs/DECISIONS.md, docs/AGENT_PLAYBOOK.md, docs/KLONE_AGENT_CONVENTIONS.md, and docs/POST_V1_1_NEXT_STEP_PROPOSAL.md.

Use verified repo evidence only.

Task:
Determine whether the proposed V1.2 bounded batch art metrics and longitudinal comparison seam is the next smallest approved art-lab substep after V1.1.

Return exactly:
1. current phase
2. what is already canonically complete
3. whether V1.2 should be approved, rejected, or revised
4. next exact smallest safe step
5. who should do it
6. exact handoff prompt
7. what not to do
8. done check
```

## Short recommendation

If the project should keep moving without breaking its own discipline, the next best move is:

1. review this proposal as `KLONE Supervisor` or `KLONE Architect`
2. if accepted, update canonical docs to approve `V1.2`
3. only then implement the smallest bounded comparison slice before any clustering, OCR, embeddings, or profiling expansion
