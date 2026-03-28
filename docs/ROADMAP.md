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

## Not approved yet
- semantic search
- embeddings
- OCR/transcription
- fuzzy matching
- autonomous reasoning layers
- agentic memory mutation
