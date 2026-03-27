# KLONE Roadmap

## Phase 2B.1
Memory spine:
- memory_events
- memory_entities
- memory_episodes
- deterministic ingest-run episodes
- read-only room-scoped memory API

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
- correction read contract lock
- migration caveat
- stability tests
- no new write surface

## Phase 2C.1
Query / retrieval primitives:
- correction-aware querying
- active / rejected / superseded visibility
- lineage traversal
- episode / event navigation
- explainability-first query behavior
- still no semantic/fuzzy behavior until core operations are stable

## Phase 2C
Broader query / retrieval layer:
- build on 2C.1 primitives only after contracts remain stable
- explainability improvements
- still no semantic/fuzzy behavior until core operations are stable
