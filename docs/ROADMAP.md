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
- initial sequence: A1.1 request-context + GET /v1/capabilities, then A1.2 append-only audit chain foundation, then A1.3 local blob metadata shell via existing asset routes
- stable object/query/changes/blob contracts
- append-only audit chain reuse/extension
- local blob metadata shell
- no distributed split, broker, gRPC, OIDC provider integration, or external object store requirement yet

## Not approved yet
- semantic search
- embeddings
- OCR/transcription
- fuzzy matching
- autonomous reasoning layers
- agentic memory mutation
