# Key Decisions

## D-001 Evidence immutability
evidence_text is never rewritten, paraphrased, or inferred.

## D-002 Room scoping
All memory mutations and reads are room-scoped. No cross-room linking.

## D-003 Replay is internal
Replay exists for deterministic maintenance and verification, not as a public feature.

## D-004 Correction without deletion
Memory rows are corrected via status and supersession, not deletion.

## D-005 Governance before intelligence
No semantic/fuzzy/agentic memory features before deterministic operations, provenance, replay, and correction are stable.
