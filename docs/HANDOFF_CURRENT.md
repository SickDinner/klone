# Current Handoff

## Current approved phase
Phase 2B.4: Memory Correction Contract Closeout

## Baseline
- 2B.1 complete
- 2B.2 complete
- 2B.3 complete or finalizing
- deterministic memory, provenance, replay, and correction layer exist

## Hard constraints
- do not modify ingest behavior
- do not modify evidence_text
- do not delete memory rows
- do not add public memory write endpoints
- do not widen scope beyond approved phase
- preserve room-scoping and replay determinism

## Immediate task
Lock correction read contract and document migration caveat for existing DBs.

## Required verification
- compile
- focused tests
- local real-app verification if behavior changed
