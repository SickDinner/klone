# Current Handoff

## Current approved phase
Phase 2C.1: Query / Retrieval primitives

## Baseline
- 2B.1 complete
- 2B.2 complete
- 2B.3 complete
- 2B.4 complete
- deterministic memory, provenance, replay, and correction layer exist

## Hard constraints
- do not modify ingest behavior
- do not modify evidence_text
- do not delete memory rows
- do not add public memory write endpoints
- do not widen scope beyond approved phase
- preserve room-scoping and replay determinism
- do not add semantic or fuzzy retrieval yet
- do not add embeddings or agentic memory behavior

## Immediate task
Implement correction-aware query and retrieval primitives:
- active / rejected / superseded visibility
- correction-aware filtering
- lineage traversal
- episode / event navigation
- explainability-first query behavior

## Required verification
- compile
- focused tests
- local real-app verification if behavior changed
