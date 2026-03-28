# Current Handoff

Last updated: 2026-03-28

## Current approved phase
Phase A1.5: Public Room-Scoped Object Get

## Baseline
- 2B.1 through 2B.5 complete
- memory spine, provenance, replay, correction, contract lock, and stress verification are in place
- read-only query, context, provenance-detail, bounded-answer, and Memory Explorer surfaces exist in repo reality
- A1.1 request context, service seams, and GET /v1/capabilities exist in repo reality
- A1.2 contract shells and append-only control-plane audit chain exist in repo reality
- A1.3 local blob metadata shell exists in repo reality without adding a new /v1 blob route
- A1.4 local object envelope shell exists in repo reality without adding a public /v1 object route
- Phase A1 roadmap bullets are satisfied in current repo reality
- A1.5 is approved but not implemented yet

## Immediate goal
Implement the smallest approved A1.5 step only:
`POST /v1/rooms/{room_id}/objects/get`.
Do not reopen completed 2C retrieval, context, provenance, bounded-answer, Memory Explorer, A1.1 seam work, A1.2 audit/contract-shell work, A1.3 blob metadata shell work, or A1.4 object envelope shell work.

## Approved scope
- one new read-only public route only: `POST /v1/rooms/{room_id}/objects/get`
- room-scoped object lookup only
- supported object kinds only: `dataset`, `asset`, `memory_event`, `memory_episode`
- reuse existing deterministic room-scoped reads and the completed A1.4 object-envelope shell
- reuse request context and append-only control-plane audit chaining
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
- do not regress the local object envelope shell or its capability/readiness visibility through /v1/capabilities
- do not add /v1 query, /v1 changes, /v1/objects/set, /v1/blobs/upload, or /v1/blobs/{blob_id}/meta in A1.5
- do not widen supported object kinds beyond `dataset`, `asset`, `memory_event`, and `memory_episode`

## Required verification
- compile pass
- focused A1 tests
- local verification because a new public read route is approved





