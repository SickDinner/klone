# Current Handoff

## Current approved phase
Phase 2C.1: Query / Retrieval Primitives

## Baseline
- 2B.1 through 2B.5 complete
- memory spine, provenance, replay, correction, contract lock, and stress verification are in place

## Immediate goal
Do not reimplement query/list provenance summary exposure, episode query, traversal, or detail-level provenance.
Identify the next exact unfinished 2C.1 read-only retrieval substep from verified repo evidence only.

## Approved scope
- docs/handoff alignment for verified 2C.1 state
- duplicate-work prevention
- identification of the next smallest in-scope 2C.1 step only
- no new runtime behavior
- no API widening

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



