# KLONE Repo Reality Deep Dive

Last updated: 2026-03-28

## Purpose

This document is a non-canonical analysis note.

Its job is to describe current repo reality as observed on 2026-03-28 without rewriting the canonical control docs:

- `PROJECT_STATUS.md`
- `HANDOFF_CURRENT.md`
- `ROADMAP.md`

Use this note to understand nuance and drift.
Do not treat it as the canonical phase-control source.

## Evidence base

This analysis is grounded in:

- current git state on `main`
- canonical docs under `docs/`
- current `HEAD` commit
- source under `src/klone/`
- focused tests under `tests/`

Observed repo state during this audit:

- branch: `main`
- branch status: ahead of `origin/main` by 1 commit
- worktree: clean
- current `HEAD`: `8f72056 feat(memory): add provenance detail reads and bounded llm answers`

## Canonical doc truth

As of the current canonical control docs:

- `Phase 2B.1` through `Phase 2B.5` are complete
- `Phase 2C.1` is marked complete
- current approved lane is `Post-2C.1 closeout / next-step selection`
- next approved action is to identify the next exact approved phase/substep from verified repo evidence only
- completed `2C.1` items recorded in canonical docs are:
  - room-scoped memory event query primitive
  - status-aware filtering for memory events
  - deterministic ordering and pagination
  - correction-aware query coverage
  - episode query primitive
  - episode-side deterministic filtering
  - episode/event traversal refinement
  - query/list provenance summary exposure

The canonical docs still explicitly forbid reopening completed `2C.1` retrieval work and still forbid widening into:

- semantic search
- embeddings
- fuzzy matching
- public write surfaces
- correction widening

## Locked architectural laws

The project still clearly defines these as non-negotiable:

- evidence immutability
- room scoping
- replay is internal
- correction without deletion
- governance before intelligence
- read-only public memory API
- provenance first

That remains the clearest moral and technical spine of KLONE.

## What repo reality already contains beyond the canonical docs

The repo is ahead of the canonical docs in at least one meaningful way.

### 1. `origin/main` already contains post-2C.1 runtime work

The visible history includes these runtime commits before the current local `HEAD`:

- `7d40cfa feat(memory): add deterministic read-only context package assembly`
- `bded850 feat(memory): add read-only deterministic context payload shell`

This means post-`2C.1` runtime work already exists in shared repo history even though the canonical docs are still phrased as `next-step selection`.

### 2. Local `HEAD` adds another post-2C.1 runtime layer

Current `HEAD` adds:

- event provenance detail reads
- episode provenance detail reads
- bounded read-only LLM answer behavior

Touched files in `HEAD` relative to `origin/main`:

- `src/klone/api.py`
- `src/klone/memory.py`
- `src/klone/schemas.py`
- `tests/test_memory_phase_2b3.py`
- `tests/test_memory_phase_2c1_provenance.py`
- `tests/test_memory_phase_2c4.py`

### 3. Current source surface now includes three distinct post-2C.1 layers

Observed in `src/klone/memory.py`:

- `assemble_context_package(...)`
- `prepare_llm_context_payload(...)`
- `generate_read_only_llm_answer(...)`
- `get_event_provenance_detail(...)`
- `get_episode_provenance_detail(...)`

Observed in `src/klone/api.py`:

- `GET /api/memory/events/{event_id}/provenance`
- `GET /api/memory/episodes/{episode_id}/provenance`

Observed in `src/klone/schemas.py`:

- provenance detail records
- context package records
- LLM context payload records
- bounded LLM answer records

In practice, repo reality has already moved from plain retrieval primitives into:

- provenance detail exposure
- deterministic read-only context packaging
- deterministic read-only LLM context payloads
- bounded read-only answer generation

## Test-backed current capability map

Focused verification during this audit:

- `python -m compileall src tests` passed
- 32 focused memory tests passed

The green test set covers:

- `2B.3` correction visibility and read-only API surface
- `2B.5` replay/correction/provenance/room-isolation stress invariants
- `2C.1` retrieval/query primitives
- provenance detail reads
- deterministic context package assembly
- deterministic read-only LLM context payloads
- bounded read-only LLM answers

This is important:

the repo is not merely carrying speculative code.
It is carrying runtime work that is both implemented and green.

## Best current interpretation of project state

The most accurate project reading is no longer:

`2C.1 complete, nothing beyond that exists`

The more truthful reading is:

`2C.1 was canonically closed out, but repo reality already contains at least a post-2C.1 read-only context/explainability layer, and local HEAD extends that further with provenance detail and bounded answer behavior.`

That does not automatically mean the new work is canonically approved.
It does mean the project can no longer pretend this runtime work does not exist.

## What is genuinely strong in this project

### 1. The invariant discipline is real

KLONE is strongest when it treats memory as governed infrastructure instead of as a clever assistant feature.

The repo repeatedly protects:

- immutable `evidence_text`
- room-scoped reads
- replay determinism
- correction through status/supersession instead of deletion
- provenance-first memory existence
- read-only public memory routes

This is the strongest design signal in the whole project.

### 2. Query/intelligence is being introduced cautiously

The current post-2C.1 code does not look like giant-agent mush.
It still looks bounded:

- source-linked
- read-only
- deterministic
- room-scoped
- explicitly limited for unsupported questions

That is exactly the right posture for early intelligence surfaces.

### 3. The repo already behaves more like a cognition stack than a chatbot

Between:

- governed ingest/index
- memory spine
- replay/correction
- retrieval primitives
- context packaging
- bounded answer surfaces

the project has clearly crossed from pure scaffold into a genuine layered cognition system.

## The current real risk

The main risk is not lack of intelligence.

The main risk is:

- canonical docs lagging behind repo truth
- multiple post-2C.1 runtime steps existing without a stable canonical phase name
- duplicate work caused by stale handoffs
- builder/verifier prompts targeting already-green areas

In short:

the repo is ahead of the signs on the wall.

## Safe conclusions

### Conclusion A

It would be incorrect to treat the repo as if only `2C.1` retrieval primitives exist.

### Conclusion B

It would also be unsafe to keep adding post-2C.1 runtime behavior without first canonically naming the lane that already exists.

### Conclusion C

The next correct move is not more runtime implementation.
The next correct move is canonical ratification of the already-existing post-2C.1 read-only context/answer layer.

## Recommended next step

Run a narrow supervisor/verifier ratification step with this exact goal:

- classify the already-implemented post-2C.1 runtime work canonically

That decision should determine whether the existing runtime work is:

1. still considered part of `2C.1` closeout,
2. the first approved substep of a new read-only post-`2C.1` phase,
3. or unapproved drift that must freeze immediately.

Only after that classification should canonical docs be updated.

Only after those docs are updated should any additional implementation be approved.

## What should not happen next

Do not:

- reopen completed `2C.1` retrieval primitives
- add semantic search
- add embeddings
- add OCR/transcription
- add fuzzy matching
- add public write memory APIs
- widen correction behavior
- invent a giant agent layer
- treat genomics/media/art/memory as one unrestricted soup
- keep stacking runtime commits on top of an unnamed lane

## One-line verdict

KLONE is no longer just a governed memory prototype.
It is already a governed retrieval-plus-context system with bounded answer surfaces, but its canonical docs have not fully caught up with that truth.
