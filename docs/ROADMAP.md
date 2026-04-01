# KLONE Roadmap

## Phase 2B.1
Memory spine:
- memory_events
- memory_entities
- memory_episodes
- deterministic ingest-run episodes
- room-scoped read-only API

## Phase 2B.2
Hardening:
- normalized provenance
- internal replay/reseed
- hydrated detail reads
- replay verification

## Phase 2B.3
Correction layer:
- active / rejected / superseded
- correction metadata
- internal reject/supersede operations
- replay preserves correction state
- dedicated memory_event_supersessions

## Phase 2B.4
Contract closeout:
- correction read contract locked
- migration/bootstrap caveat documented
- stability tests
- no new write surface

## Phase 2B.5
Stress / invariant verification:
- replay/correction stress cases
- room isolation adversarial checks
- provenance stability checks
- legacy SQLite bootstrap tolerance
- no runtime feature expansion

## Phase 2B.6
Read-Only Dialogue Corpus Shell:
- POST /api/dialogue-corpus/analyze
- read-only local conversation-export analysis only
- support extracted Facebook/Messenger export roots and ChatGPT conversation export JSON files already present on disk
- expose relationship, network, style, and timeline priors only when the source format actually supports them
- allow root-folder discovery that selects the richest Messenger export candidate without blindly merging partial exports
- Mission Control dialogue corpus panel
- no memory writes, no durable identity labels, no OCR/transcription, no embeddings, and no sentiment or psychological inference in this phase

## Phase 2B.7
Bounded Dialogue Query Shell:
- POST /api/dialogue-corpus/answer
- local `klone` CLI command for bounded dialogue-corpus querying
- reuse the completed 2B.6 aggregate export analysis rather than adding a raw semantic retrieval layer
- support only bounded aggregate question classes: summary, top direct ties, top groups, network shape, timeline, owner-side style, topic hints, and named counterpart lookup
- keep named counterpart lookup structural and thread-backed; do not summarize raw message meaning or relationship psychology
- no memory writes, no durable identity labels, no raw-message semantic search, no embeddings, no OCR/transcription, and no sentiment or psychological inference in this phase

## Phase 2B.8
Clone Chat Room Shell:
- GET /api/clone-chat/status
- POST /api/clone-chat/respond
- GET /chat
- IRC-style local chat room for testing the bounded clone shell in browser
- reuse the completed 2B.7 bounded dialogue answer surface rather than introducing free-form memory retrieval
- allow optional GPT-5.4 rendering through the OpenAI Responses API only when OPENAI_API_KEY is configured
- preserve bounded evidence grounding, unsupported-question gating, and no-memory-write behavior even when GPT rendering is enabled
- no raw-message semantic retrieval, no embeddings, no autonomous roleplay loop, and no durable memory writes in this phase

## Phase 2C.1
Query / Retrieval Primitives:
- status-aware filtering
- event/episode traversal
- correction-aware visibility
- provenance-aware retrieval
- deterministic ordering and pagination

## Phase 2C.2
Read-Only Context Package Assembly:
- deterministic context package assembly
- room-scoped event/episode context packaging
- correction summary exposure
- provenance summary exposure

## Phase 2C.3
Read-Only LLM Context Payload:
- deterministic payload construction
- explicit included/excluded context visibility
- read-only interface shell
- memory write path disabled

## Phase 2C.4
Bounded Read-Only Answer Surfaces:
- event provenance detail retrieval
- episode provenance detail retrieval
- bounded source-linked answer path
- unsupported question gating
- room-isolated answer generation

## Phase 2C.5
Public Read-Only Delivery Surface:
- public read-only context package API route
- public read-only LLM context payload API route
- public bounded read-only memory answer API route
- Mission Control Memory Explorer UI
- focused route coverage for the new read-only surface

## Phase A1
Public Control-Plane Skeleton:
- versioned /v1 API shell inside the existing FastAPI app
- request context with request_id / trace_id / principal placeholder
- in-process service seams for MemoryFacade / PolicyService / AuditService / BlobService
- initial sequence: A1.1 request-context + GET /v1/capabilities, then A1.2 append-only audit chain foundation, then A1.3 local blob metadata shell via existing asset routes, then A1.4 local object envelope shell via existing read routes, then A1.5 public room-scoped object get, then A1.6 public room-scoped query shell, then A1.7 public room-scoped blob metadata detail, then A1.8 public room-scoped audit preview query kind
- stable object/query/changes/blob contracts
- append-only audit chain reuse/extension
- local blob metadata shell
- no distributed split, broker, gRPC, OIDC provider integration, or external object store requirement yet

## Phase A1.4
Local Object Envelope Shell:
- deterministic read-only object envelope projection
- existing object kinds only: dataset, asset, memory_event, memory_episode
- reuse existing read routes and service seams
- capability/readiness visibility through /v1/capabilities only
- no public /v1/objects/get route yet

## Phase A1.5
Public Room-Scoped Object Get:
- POST /v1/rooms/{room_id}/objects/get only
- read-only object lookup only
- supported object kinds only: dataset, asset, memory_event, memory_episode
- backed by the completed A1.4 local object-envelope shell and existing deterministic room-scoped reads
- append-only control-plane audit chaining reused for the new route
- no query route, changes route, object set route, or blob route in this phase

## Phase A1.6
Public Room-Scoped Query Shell:
- POST /v1/rooms/{room_id}/query
- read-only query only
- supported query kinds only: memory_events and memory_episodes
- backed by the existing deterministic governed memory list reads
- preserve status-aware filtering, deterministic ordering, and pagination semantics
- append-only control-plane audit chaining reused for the new route
- no semantic search, embeddings, fuzzy matching, changes route, object set route, or blob route in this phase

## Phase A1.7
Public Room-Scoped Blob Metadata Detail:
- GET /v1/rooms/{room_id}/blobs/{blob_id}/meta
- read-only blob metadata detail only
- backed by the existing local blob metadata shell and deterministic asset-backed blob ids
- preserve linked_object_id visibility and room-scoped asset ownership
- append-only control-plane audit chaining reused for the new route
- no upload route, blob mutation, blob list/query route, or external object store semantics in this phase

## Phase A1.8
Public Room-Scoped Audit Preview Query Kind:
- POST /v1/rooms/{room_id}/query only
- read-only query extension only
- supported new query kind only: audit_preview
- backed by the existing deterministic room-scoped /api/audit preview surface
- preserve deterministic limit/offset pagination and bounded event_type/target_type filtering
- summarize permission only for audit_preview; do not widen room read behavior
- append-only control-plane audit chaining reused for the query extension
- no new /v1 route, no semantic search, no embeddings, no fuzzy matching, and no changes/write surface

## Phase A1.9
Public Room-Scoped Change Preview Seam:
- GET /v1/rooms/{room_id}/changes only
- read-only change preview only
- backed by the existing deterministic room-scoped /api/audit preview surface
- preserve deterministic limit/offset pagination and bounded event_type/target_type filtering
- summarize permission only; do not widen room read behavior
- append-only control-plane audit chaining reused for the new route
- no write surface, no change detail route, no semantic search, no embeddings, and no fuzzy matching

## Phase G1
Governed Ingest Spine:
- make ingest visible before writes rather than treating scan as a blind submit
- keep classification, room routing, dedup, and planned asset actions inspectable
- preserve bounded manifest history for completed ingest runs
- extend the Mission Control intake experience without introducing async workers yet
- preserve current deterministic local ingest semantics and audit-backed scan execution

## Phase G1.1
Read-Only Ingest Preflight Manifest:
- POST /api/ingest/preflight
- reuse the existing DatasetIngestRequest shape
- read-only preview only; no dataset, asset, ingest_run, or audit writes
- resolve normalized root path, room routing, and guard decisions before scan
- estimate planned new/updated/unchanged asset counts and duplicate candidates
- expose bounded asset-kind breakdown plus bounded sample asset rows
- Mission Control intake UI shows the manifest before the user starts the actual scan

## Phase G1.2
Bounded Ingest Run Manifest History:
- GET /api/ingest/runs/{run_id}/manifest
- read-only manifest history only
- persist a bounded manifest snapshot when a real ingest run completes
- preserve per-run manifest visibility even after later rescans mutate current asset rows
- expose total_size_bytes, asset-kind breakdown, bounded sample assets, and warnings for the stored run snapshot
- use summarize-compatible room access rather than raw asset read requirements
- Mission Control ingest-run history can inspect stored manifest snapshots
- no resumable queue, no background worker orchestration, and no preview persistence in this phase

## Phase G1.3
Local Ingest Queue Shell:
- POST /api/ingest/queue
- POST /api/ingest/queue/{job_id}/execute
- POST /api/ingest/queue/{job_id}/cancel
- local queue shell only
- reuse the existing deterministic ingest execution path rather than introducing a new worker runtime
- allow explicit operator staging, execute, retry-after-failure, and cancel-before-run control
- Mission Control exposes queue depth plus recent queue job visibility
- no resumable interruption state, no background workers, and no startup auto-resume in this phase

## Phase G1.4
Local Resumable Ingest Queue:
- no new queue route; reuse the existing local queue shell
- startup recovery marks orphaned local running jobs as interrupted
- interrupted jobs remain room-scoped, visible, and manually resumable through POST /api/ingest/queue/{job_id}/execute
- queue depth counts queued and interrupted jobs that still need operator attention
- Mission Control exposes interrupted-run visibility and Resume copy without auto-executing scans
- append-only audit records capture startup interruption recovery
- no background workers, no automatic startup execution, and no distributed worker runtime in this phase

## Phase G1.5
Bounded Ingest Queue History Seam:
- GET /api/ingest/queue/{job_id}/history
- read-only queue history/detail only
- reuse existing `ingest_queue_jobs`, append-only `audit_events`, and linked ingest run / manifest references only
- preserve room scope, deterministic ordering, and bounded history visibility
- make interrupted, resumed, completed, failed, and cancelled lifecycle transitions inspectable when already present in stored evidence
- no new queue states, no automatic resume/execute, no background workers, and no `/v1` widening in this phase

## Phase V1
Read-Only Art and Drawing Lab:
- add deterministic formal visual metrics over existing governed image assets
- keep the surface read-only and asset-backed
- block personality profiling and clinical-style interpretation
- expose art-lab readiness through Mission Control and public capability visibility
- do not widen into OCR, embeddings, batch profiling, or longitudinal inference in the first step

## Phase V1.1
Read-Only Asset Formal Metrics:
- GET /api/art/assets/{asset_id}/metrics
- single asset, room-scoped image analysis only
- deterministic size, brightness, contrast, edge-density, symmetry, balance, entropy, and colorfulness metrics
- capability visibility through /v1/capabilities
- Mission Control asset detail shows an Art Metrics panel for supported image assets
- no OCR, no embeddings, no batch comparison surface, and no personality or clinical inference

## Phase V1.2
Bounded Batch Art Metrics and Longitudinal Comparison:
- GET /api/art/assets/compare
- read-only room-scoped comparison only
- compare only an explicit bounded set of existing image assets
- reuse the existing deterministic V1.1 formal metrics set; do not invent new learned features
- preserve deterministic ordering by existing asset timestamps with stable tie-breaks
- expose ordered side-by-side metric values plus simple first-to-last metric deltas only
- no OCR, no embeddings, no semantic similarity, no clustering, no profiling, no batch writeback, and no /v1 expansion

## Phase 2E.1
Read-Only Constitution Layer Shell:
- GET /api/constitution
- read-only constitution snapshot only
- expose slow-cycle parameter defaults, approval state, and append-only change notes
- keep constitution state separate from memory rows, ingest evidence, and room-scoped query results
- surface constitution seam visibility through Mission Control and /v1/capabilities
- no write route, no live routing influence, no self-modification loop, and no agent authority expansion in this phase

## Not approved yet
- post-2B.8 dialogue expansion
- post-2E.1 constitution expansion
- post-V1.2 art-lab expansion
- semantic search
- embeddings
- OCR/transcription
- fuzzy matching
- autonomous reasoning layers
- agentic memory mutation
