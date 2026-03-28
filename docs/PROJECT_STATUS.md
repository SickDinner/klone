# PROJECT STATUS

Last updated: 2026-03-28

## Current phase
Phase A1.9 complete; no further approved A1 or G1 substep is defined yet

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
- Phase A1.4 complete
- Phase A1 complete
- Phase A1.5 complete
- Phase A1.6 complete
- Phase A1.7 complete
- Phase A1.8 complete
- Phase A1.9 complete
- Phase G1 approved
- Phase G1.1 complete
- Phase G1.2 complete
- Phase G1.3 complete

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

## Completed in A1.4
- local object envelope shell via existing read routes
- deterministic read-only projection for dataset, asset, memory_event, and memory_episode
- room-scoped underlying reads only
- /v1/capabilities exposes readiness and object-shell backing routes, but no public /v1/objects/get route exists
- no ingest, replay, correction, or evidence_text behavior changes
- focused A1.4 tests green
- full unittest suite green
- local HTTP smoke green for object-shell readiness and existing four service seams

## Completed in A1.5
- first public room-scoped read-only object lookup seam
- POST /v1/rooms/{room_id}/objects/get only
- support only existing object kinds already justified by repo reality: dataset, asset, memory_event, memory_episode
- back the route with existing deterministic room-scoped reads and the completed A1.4 object-envelope shell
- reuse request context and append-only control-plane audit chaining
- no ingest, replay, correction, or evidence_text behavior changes
- focused A1.5 tests green
- local HTTP smoke green for public room-scoped object get and audit-chain writes

## Completed in A1.6
- first public room-scoped query shell
- POST /v1/rooms/{room_id}/query only
- support only existing deterministic read-only query kinds already justified by repo reality: memory_events and memory_episodes
- preserve existing status-aware filtering, deterministic ordering, and pagination semantics
- reuse request context and append-only control-plane audit chaining
- no semantic search, fuzzy matching, embeddings, or query-time synthesis
- no ingest, replay, correction, or evidence_text behavior changes
- focused A1.6 tests green
- local HTTP smoke green for public room-scoped query reads and audit-chain writes

## Completed in A1.7
- first public room-scoped blob metadata detail seam
- GET /v1/rooms/{room_id}/blobs/{blob_id}/meta only
- support only the existing deterministic asset-backed blob metadata shell already justified by repo reality
- preserve deterministic blob_id and linked_object_id mapping over governed asset rows
- reuse request context and append-only control-plane audit chaining
- no upload route, no blob mutation, no external object store semantics, and no ingest/replay/correction/evidence_text behavior changes
- focused A1.7 tests green
- full unittest suite green
- local HTTP smoke green for public room-scoped blob metadata detail and audit-chain writes

## Completed in A1.8
- public room-scoped query shell widened by one safe query kind only: audit_preview
- POST /v1/rooms/{room_id}/query remains the only public query route
- audit preview is backed by the existing deterministic room-scoped /api/audit surface
- deterministic limit/offset pagination preserved for audit preview queries
- bounded event_type and target_type filtering exposed for audit preview queries
- audit preview uses summarize permission without widening room read access
- query-shell contract and capability copy updated to reflect audit preview support
- focused A1.8 tests green
- full unittest suite green
- compile pass green

## Completed in A1.9
- first public room-scoped change preview seam
- GET /v1/rooms/{room_id}/changes only
- change preview is backed by the existing deterministic room-scoped /api/audit preview surface
- deterministic limit/offset pagination preserved for change preview reads
- bounded event_type and target_type filtering exposed for change preview reads
- summarize permission only; no room-read widening for change preview
- change-shell contract and capability copy updated to reflect public read-only change preview availability
- focused A1.9 tests green
- full unittest suite green
- compile pass green

## Completed in G1.1
- first governed ingest preflight manifest surface
- POST /api/ingest/preflight reuses the existing DatasetIngestRequest shape
- preview resolves normalized root path, room routing, and guard decisions without writing datasets, assets, ingest runs, or audit rows
- preview estimates planned new/updated/unchanged asset actions and duplicate candidates using the same dedup semantics as ingest
- bounded asset-kind breakdown and sample asset rows are exposed for Mission Control intake review
- Mission Control intake UI now supports Preview Manifest before Scan Dataset
- focused G1.1 tests green
- full unittest suite green
- compile pass green

## Completed in G1.2
- first bounded ingest run manifest history surface
- GET /api/ingest/runs/{run_id}/manifest exposes a stored manifest snapshot for a completed run
- ingest completion now persists bounded manifest history with total_size_bytes, asset-kind breakdown, sample assets, and warnings
- run manifests remain readable even after later rescans mutate current asset rows
- ingest status/list payloads now surface has_manifest visibility for run history
- Mission Control ingest-run history now supports Inspect Manifest and auto-opens the latest successful scan result
- focused G1.2 tests green
- regression slice for G1.1 green
- compile pass green

## Completed in G1.3
- first local ingest queue shell over the existing governed ingest spine
- POST /api/ingest/queue stages or reuses a bounded local ingest queue job without executing the scan immediately
- POST /api/ingest/queue/{job_id}/execute performs explicit operator-triggered queue execution through the existing deterministic ingest path
- POST /api/ingest/queue/{job_id}/cancel cancels queued or failed jobs without widening into async interruption semantics
- GET /api/ingest/queue and GET /api/ingest/status expose queue depth plus recent job visibility
- Mission Control now shows queue staging, inspect, execute, cancel, and manifest handoff controls
- focused G1.3 tests green
- full unittest suite green
- compile pass green

## Next approved substep
- no further approved A1 or G1 substep is enumerated in canonical repo evidence
- require explicit roadmap extension or approval before widening the public control-plane seam beyond the completed A1.9 change preview route or the ingest spine beyond the completed G1.3 local queue shell
- do not reopen completed 2C retrieval, context, provenance, bounded-answer, Memory Explorer, A1.1 seam work, A1.2 audit/contract-shell work, A1.3 blob metadata shell work, A1.4 object envelope shell work, A1.5 public object-get seam work, A1.6 public query seam work, A1.7 public blob-meta seam work, A1.8 audit preview query work, G1.1 preflight manifest work, G1.2 manifest history work, or G1.3 local queue shell work

