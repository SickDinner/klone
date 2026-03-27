# Current Handoff

## Current approved phase
Phase 2C.1: Query / Retrieval Primitives

## Baseline
- 2B.1 complete
- 2B.2 complete
- 2B.3 complete
- 2B.4 complete
- memory spine, provenance, replay, correction, and correction contract are in place

## Immediate goal
Add the smallest safe query/retrieval layer on top of the stabilized memory system.

## Approved scope
- room-scoped query primitives
- status-aware filtering
- event/episode traversal
- correction-aware retrieval
- deterministic ordering/pagination
- provenance-aware detail traversal

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
