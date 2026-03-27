# KLONE Project Status

## Current phase
Phase 2B.4 complete.
Next step: Phase 2C.1 Query / Retrieval primitives.

## Completed
- Phase 2B.1: deterministic memory spine
- Phase 2B.2: normalized provenance + internal replay + hydrated detail reads
- Phase 2B.3: correction layer + dedicated event supersession storage
- Phase 2B.4: correction contract closeout + migration caveat + read stability

## Invariants
- evidence_text is immutable
- no inferred or synthetic evidence
- room-scoped only
- replay must be idempotent
- replay must preserve correction state
- no public memory write endpoints
- provenance must remain source-linked

## Current repo expectations
- main is source of truth
- feature work must stay tightly scoped
- every phase ends with compile + tests + local real-app verification

## Next approved phase
Phase 2C.1: correction-aware query and retrieval primitives
