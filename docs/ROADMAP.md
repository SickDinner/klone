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
- initial sequence: A1.1 request-context + GET /v1/capabilities, then A1.2 append-only audit chain foundation, then A1.3 local blob metadata shell via existing asset routes, then A1.4 local object envelope shell via existing read routes, then A1.5 public room-scoped object get, then A1.6 public room-scoped query shell, then A1.7 public room-scoped blob metadata detail, then A1.8 public room-scoped audit preview query kind, then A1.9 public room-scoped change preview seam
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

## Not approved yet
- semantic search
- embeddings
- OCR/transcription
- fuzzy matching
- autonomous reasoning layers
- agentic memory mutation
