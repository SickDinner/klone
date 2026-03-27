# Current Handoff

## Current approved phase
Phase 2B.4: Memory Correction Contract Closeout

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
Close out Phase 2B.4 cleanly:
- keep correction read contract locked
- keep migration caveat documented
- keep replay / evidence / provenance / room isolation guarantees explicit
- do not start Phase 2C.1 in this handoff

## Next approved phase after closeout
Phase 2C.1: Query / Retrieval primitives

## Required verification
- compile
- focused tests
- local real-app verification if behavior changed
