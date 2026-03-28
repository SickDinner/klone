# PROJECT STATUS

Last updated: 2026-03-28

## Current phase
Phase A1 complete; no further approved post-A1 substep is defined yet

## Phase state
- Phase 2B.1 complete
- Phase 2B.2 complete
- Phase 2B.3 complete
- Phase 2B.4 complete
- Phase 2B.5 complete
- Phase 2C.1 complete
- Phase 2C.2 complete
- Phase 2C.3 complete
- Phase 2C.4 complete
- Phase 2C.5 complete
- Phase A1 approved
- Phase A1.1 complete
- Phase A1.2 complete
- Phase A1.3 complete
- Phase A1 complete

## Completed in 2B.5
- stress verification for replay/correction/provenance/room isolation
- adversarial local e2e against temporary SQLite DB
- scoped replay isolation verified
- correction state preservation verified
- provenance and evidence immutability verified
- no runtime feature expansion


## Completed in 2C.1
- room-scoped memory event query primitive
- status-aware filtering for memory events
- deterministic ordering and pagination
- correction-aware query coverage
- 2B.2 / 2B.3 / 2C.1 tests verified
- episode query primitive
- episode-side deterministic filtering
- episode/event traversal refinement
- detail-level provenance exposure
- query/list provenance summary exposure

## Completed in 2C.2
- deterministic read-only context package assembly
- room-scoped event/episode context packaging
- correction-aware context summaries
- provenance summary exposure in assembled context

## Completed in 2C.3
- read-only deterministic LLM context payload shell
- exact included/excluded context visibility
- explicit read-only interface mode
- memory write path disabled in context payload

## Completed in 2C.4
- room-scoped event provenance detail route
- room-scoped episode provenance detail route
- bounded read-only LLM answer path
- unsupported question gating for bounded answer path
- source-linked bounded answer behavior
- room isolation preserved for bounded answer generation

## Completed in 2C.5
- public read-only context package API route
- public read-only LLM context payload API route
- public bounded read-only memory answer API route
- Mission Control Memory Explorer UI
- focused route coverage for the new read-only surface
- full unittest suite green after surface update

## Completed in A1.1
- request context middleware with request_id / trace_id / principal / actor_role placeholders
- request context headers on existing and new routes
- explicit in-process service seams for MemoryFacade / PolicyService / AuditService / BlobService
- versioned public GET /v1/capabilities route
- focused A1.1 tests green
- full unittest suite green
- local HTTP smoke green for /v1/capabilities

## Completed in A1.2
- stable public object/query/change/blob contract shells published through GET /v1/capabilities
- append-only public control-plane audit chain for GET /v1/capabilities
- request_id / trace_id / principal / actor_role captured in chained control-plane audit rows
- deterministic prev_event_hash -> event_hash linking
- no new /v1 routes added
- focused A1.2 tests green
- full unittest suite green
- local HTTP smoke green for audit-chain linkage

## Completed in A1.3
- local blob metadata shell projects governed asset rows into a stable read-only blob metadata record
- BlobService exposes deterministic blob_id and linked_object_id mapping over existing asset rows
- GET /v1/capabilities exposes blob metadata list/detail capability visibility via existing /api/assets routes
- no new /v1 blob route added
- focused A1.3 tests green
- full unittest suite green
- local HTTP smoke green for blob-service seam visibility

## Next approved substep
- no further approved post-A1 substep is enumerated in docs/ROADMAP.md
- require explicit roadmap extension or approval before widening the /v1 control-plane surface
- do not reopen completed 2C retrieval, context, provenance, bounded-answer, Memory Explorer, A1.1 seam work, A1.2 audit/contract-shell work, or A1.3 blob metadata shell work

