# Current Handoff

Last updated: 2026-03-28

## Current approved phase
Phase A1.4: Local Object Envelope Shell

## Baseline
- 2B.1 through 2B.5 complete
- memory spine, provenance, replay, correction, contract lock, and stress verification are in place
- read-only query, context, provenance-detail, bounded-answer, and Memory Explorer surfaces exist in repo reality
- A1.1 request context, service seams, and GET /v1/capabilities exist in repo reality
- A1.2 contract shells and append-only control-plane audit chain exist in repo reality
- A1.3 local blob metadata shell exists in repo reality without adding a new /v1 blob route
- object-shell contract already exists in /v1/capabilities but is not yet materialized as a local object envelope projection

## Immediate goal
Implement the smallest approved A1.4 step only:
local object envelope shell via existing read routes.
Do not reopen completed 2C retrieval, context, provenance, bounded-answer, Memory Explorer, A1.1 seam work, A1.2 audit/contract-shell work, or A1.3 blob metadata shell work.

## Approved scope
- deterministic read-only object envelope projection
- existing object kinds only: dataset, asset, memory_event, memory_episode
- room-scoped underlying reads only
- capability/readiness visibility through /v1/capabilities only
- reuse existing routes and service seams
- no unrelated runtime behavior
- no unrelated API widening

## Hard constraints
- do not modify ingest behavior
- do not modify evidence_text
- do not add public write endpoints
- do not add semantic search
- do not add embeddings
- do not add fuzzy matching
- do not widen correction behavior
- do not add direct LLM-to-database authority
- preserve room scope and replay determinism
- do not regress the read-only context/answer contract
- do not regress the request-context seam
- do not regress the contract shells or append-only audit-chain linkage on /v1/capabilities
- do not regress the local blob metadata shell or its capability exposure via existing asset routes
- do not add public /v1/objects/get yet
- do not add /v1 query, /v1 changes, /v1 objects/get, /v1 objects/set, /v1 blobs/upload, or /v1/blobs/{blob_id}/meta yet

## Required verification
- compile pass
- focused A1 tests
- local verification if read behavior changes





