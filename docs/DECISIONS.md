# KLONE Decisions

## D-001 Evidence immutability
evidence_text is never rewritten, paraphrased, inferred, or synthesized.

## D-002 Room scoping
All reads and mutations are room-scoped. No cross-room linkage or leakage.

## D-003 Replay is internal
Replay exists for deterministic maintenance, verification, and repair. It is not a public feature.

## D-004 Correction without deletion
Memory rows are corrected by status and supersession, not deletion.

## D-005 Governance before intelligence
No semantic/fuzzy/embedding/agentic memory expansion before deterministic operations are stable.

## D-006 Read-only public memory API
Public memory routes remain read-only unless explicitly approved by roadmap and handoff.

## D-007 Provenance first
If memory cannot be tied to exact source lineage, it should not exist as authoritative memory.
