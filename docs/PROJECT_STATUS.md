# KLONE Project Status

## Current phase
Phase 2B.4 complete.

## Phase state
- Phase 2B.1 complete
- Phase 2B.2 complete
- Phase 2B.3 complete
- Phase 2B.4 complete
- Next approved phase: Phase 2C.1 Query / Retrieval Primitives

## Completed capabilities
- deterministic memory spine
- room-scoped memory events, entities, episodes
- normalized provenance
- internal replay / reseed
- hydrated read-only detail routes
- correction layer for events and episodes
- dedicated memory_event_supersessions
- correction audit coverage
- replay preserves correction state
- correction read contract locked
- migration/bootstrap caveat documented

## Locked invariants
- evidence_text is immutable
- no inferred or synthetic evidence
- room-scoped only
- no cross-room leakage
- replay is deterministic and idempotent
- replay preserves correction state
- provenance remains source-linked
- public memory API remains read-only
- governance before intelligence

## Current merge status
Phase 2B.4: merge-safe / closeout complete

## Next approved work
Phase 2C.1:
- query / retrieval primitives
- correction-aware filtering
- lineage traversal
- deterministic read behavior
- no semantic search
- no embeddings
- no fuzzy matching
