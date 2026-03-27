# Current Handoff

## Current approved phase
Phase 2C.1: Query / Retrieval Primitives

## Baseline
- 2B.1 complete
- 2B.2 complete
- 2B.3 complete
- 2B.4 complete
- 2C.1 step 1 complete:
  - room-scoped memory event query primitive
  - status-aware filtering
  - deterministic ordering/pagination
  - correction-aware query coverage
  - tests verified

## Immediate goal
Implement the next smallest safe 2C.1 substep:
episode query primitive plus episode/event traversal refinement.

## Approved scope
- room-scoped episode retrieval
- status-aware filtering for episodes
- deterministic ordering/pagination
- read-only traversal between episodes and linked events
- correction-aware visibility
- provenance-aware detail traversal only if already supported by current shapes

## Hard constraints
- do not modify ingest behavior
- do not modify evidence_text
- do not add public write endpoints
- do not add semantic search
- do not add embeddings
- do not add fuzzy matching
- do not widen correction behavior
- preserve room scope and replay determinism

## Required verification
- compile pass
- focused tests
- local verification if read behavior changes
