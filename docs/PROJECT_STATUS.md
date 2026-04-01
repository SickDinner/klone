# PROJECT STATUS

Last updated: 2026-04-01

## Current phase
Phase V1.3 complete; no further approved 2B, 2E, A1, G1, or V1 substep is defined yet

## Phase state
- Phase 2B.1 complete
- Phase 2B.2 complete
- Phase 2B.3 complete
- Phase 2B.4 complete
- Phase 2B.5 complete
- Phase 2B.6 complete
- Phase 2B.7 complete
- Phase 2B.8 complete
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
- Phase G1.4 complete
- Phase G1.5 complete
- Phase 2E.1 complete
- Phase V1 approved
- Phase V1.1 complete
- Phase V1.2 complete
- Phase V1.3 complete

## Completed in 2B.5
- stress verification for replay/correction/provenance/room isolation
- adversarial local e2e against temporary SQLite DB
- scoped replay isolation verified
- correction state preservation verified
- provenance and evidence immutability verified
- no runtime feature expansion

## Completed in 2B.6
- first read-only dialogue corpus shell over local conversation exports
- POST `/api/dialogue-corpus/analyze` accepts extracted Facebook/Messenger export roots and ChatGPT conversation export JSON files
- root-folder discovery selects the richest Messenger JSON export candidate rather than blindly merging partial exports
- Messenger analysis exposes relationship breadth, direct-thread tie strength, group-thread visibility, activity-by-year, and owner-side style signals without writing memory rows
- ChatGPT export analysis exposes prompt-style, topic, and timeline priors while explicitly withholding human relationship-graph claims
- Mission Control now includes a Dialogue Corpus panel for running the analysis from the cockpit
- `/v1/capabilities` now exposes the dialogue-corpus service seam and capability
- focused 2B.6 tests green
- compile pass green

## Completed in 2B.7
- bounded read-only dialogue question shell over the completed 2B.6 aggregate corpus analysis
- POST `/api/dialogue-corpus/answer` now answers supported dialogue-corpus questions without enabling memory writes or raw semantic retrieval
- supported bounded query classes are summary, top direct ties, top groups, network shape, timeline, owner-side style, topic hints, and named counterpart lookup
- named counterpart lookup stays structural and thread-backed rather than inferring relationship meaning or psychology from raw message text
- repo now exposes a local `klone` CLI command for direct parser testing against a source path such as `C:\META`
- `/v1/capabilities` now exposes the dialogue-corpus answer capability alongside the existing analysis capability
- focused 2B.7 tests green
- compile pass green

## Completed in 2B.8
- first browser-based clone chat room over the bounded dialogue-corpus shell
- GET `/chat` now serves an IRC-style local test room for trying the clone interactively in browser
- GET `/api/clone-chat/status` reports default source-path readiness, preferred model, and whether OpenAI-backed rendering is configured
- POST `/api/clone-chat/respond` reuses the completed 2B.7 bounded answer surface and keeps unsupported-question gating intact
- when `OPENAI_API_KEY` is configured, chat can render through GPT-5.4 via the OpenAI Responses API; otherwise it falls back to bounded local replies without blocking the room
- the phase remains read-only and does not enable raw-message semantic retrieval, embeddings, autonomous roleplay loops, or memory writes
- focused 2B.8 tests green
- compile pass green


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

## Completed in G1.4
- local resumable queue recovery over the existing governed ingest spine
- startup now marks orphaned local `running` queue jobs as `interrupted` rather than leaving them stuck invisibly
- POST /api/ingest/queue/{job_id}/execute now safely resumes `interrupted` jobs through the existing deterministic ingest path
- POST /api/ingest/queue/{job_id}/cancel now also handles `interrupted` jobs without widening into async worker cancellation semantics
- POST /api/ingest/queue now reuses an interrupted job for the same room/root path instead of staging a duplicate
- GET /api/ingest/queue and GET /api/ingest/status now surface `interrupted` jobs as pending operator work and preserve bounded queue visibility
- startup writes append-only `ingest_queue_interrupted` audit rows for recovered jobs
- Mission Control now shows Resume copy and interrupted-run recovery context without auto-executing scans
- focused G1.4 tests green
- full unittest suite green
- compile pass green

## Completed in G1.5
- first bounded room-scoped ingest queue history/detail seam over the existing governed queue shell
- GET `/api/ingest/queue/{job_id}/history` now exposes deterministic queue lifecycle audit history for one room-scoped queue job
- queue history is bounded by `limit` and ordered chronologically from existing append-only audit evidence only
- linked ingest run visibility is exposed when present, and manifest linkage remains reference-only via `linked_manifest_available` and `linked_manifest_route`
- Mission Control queue inspect now loads bounded queue lifecycle history without adding write controls or background behavior
- the phase remains read-only and does not add new queue states, automatic resume/execute, worker runtime, or `/v1` widening
- focused G1.5 tests green
- full unittest suite green
- compile pass green

## Completed in V1.1
- first read-only Art and Drawing Lab seam over existing governed image assets
- GET `/api/art/assets/{asset_id}/metrics` returns deterministic formal image metrics for one supported asset
- formal metrics include size, aspect ratio, brightness, contrast, edge density, ink coverage, colorfulness, entropy, symmetry, and darkness center-of-mass balance
- non-image assets are rejected explicitly rather than being force-fit into pseudo-analysis
- `/v1/capabilities` now exposes the art-lab service seam and asset formal metrics capability
- Mission Control Asset Detail now includes an Art Metrics panel for supported image assets
- the phase remains read-only and explicitly avoids OCR, embeddings, personality profiling, and clinical inference
- focused V1.1 tests green
- full unittest suite green
- compile pass green

## Completed in V1.2
- bounded room-scoped art comparison seam over existing governed image assets
- GET `/api/art/assets/compare` compares an explicit bounded asset set using the existing deterministic V1.1 formal metrics only
- comparison ordering is deterministic by `fs_modified_at` with asset-id tie-breaks
- output exposes exact ordered asset metrics plus first-to-last metric deltas only
- room scope remains mandatory and cross-room asset selection is blocked
- non-image assets are rejected explicitly rather than being force-fit into comparison output
- `/v1/capabilities` now exposes the art comparison capability without widening into a new `/v1` route
- the phase remains read-only and explicitly avoids OCR, embeddings, semantic similarity, clustering, personality profiling, and clinical inference
- focused V1.2 tests green
- full unittest suite green
- compile pass green

## Completed in V1.3
- first read-only 2.5D depth-map shell over transient uploads and existing governed image assets
- POST `/api/art/depth-map` now renders a deterministic local depth approximation for one uploaded browser image or one existing image asset
- the response includes original preview, grayscale depth-map preview, and colorized relief preview without writing a derived asset row
- Mission Control Asset Detail now includes a drag-and-drop `2.5D Depth Mapper` panel plus a shortcut to reuse the selected indexed image asset
- the phase remains read-only and explicitly avoids learned monocular-depth models, OCR, embeddings, segmentation writeback, asset creation, and `/v1` widening
- focused V1.3 tests green
- compile pass green

## Completed in 2E.1
- first read-only Constitution Layer shell over slow-cycle model defaults
- GET `/api/constitution` returns a visible constitution snapshot with parameter defaults, approval state, and append-only recent change notes
- constitution state is explicitly separated from memory rows, ingest evidence, and room-scoped query results
- `/v1/capabilities` now exposes the constitution service seam and constitution snapshot capability
- Mission Control now includes a Constitution Layer panel for inspecting the current read-only shell
- the phase remains read-only and explicitly avoids write routes, self-modification, and live routing influence
- focused 2E.1 tests green
- full unittest suite green
- compile pass green

## Next approved substep
- no further approved 2B, 2E, A1, G1, or V1 substep is enumerated in canonical repo evidence
- require explicit roadmap extension or approval before widening the dialogue-corpus shell beyond the completed 2B.8 clone-chat route, the constitution layer beyond the completed 2E.1 read-only shell, the public control-plane seam beyond the completed A1.9 change preview route, the ingest spine beyond the completed G1.5 bounded queue history seam, or the art-lab beyond the completed V1.3 transient depth-map shell
- do not reopen completed 2C retrieval, context, provenance, bounded-answer, Memory Explorer, A1.1 seam work, A1.2 audit/contract-shell work, A1.3 blob metadata shell work, A1.4 object envelope shell work, A1.5 public object-get seam work, A1.6 public query seam work, A1.7 public blob-meta seam work, A1.8 audit preview query work, A1.9 change preview seam work, G1.1 preflight manifest work, G1.2 manifest history work, G1.3 local queue shell work, G1.4 local resumable queue work, G1.5 queue history work, V1.1 asset formal metrics work, V1.2 bounded comparison work, V1.3 depth-map shell work, or 2E.1 constitution shell work

