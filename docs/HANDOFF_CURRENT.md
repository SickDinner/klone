# Current Handoff

## Current approved phase
Phase 2C.1: Query / Retrieval Primitives

## Baseline
- 2B.1 through 2B.5 complete
- memory spine, provenance, replay, correction, contract lock, and stress verification are in place

## Immediate goal
Implement the next smallest safe 2C.1 substep: provenance-aware retrieval on query/list surfaces only.
Do not reimplement episode query primitive, episode traversal, or detail-level provenance that already exists.

## Approved scope
- read-only provenance summary or exact source-lineage exposure on query/list results
- room-scoped behavior only
- deterministic ordering/pagination unchanged
- correction-aware visibility unchanged
- no new runtime behavior outside this narrow read-path surface

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


