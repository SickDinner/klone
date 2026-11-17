# KLONE next-stage verification matrix (proposal, no phase approval)

This document is a **design and test plan**, not authorization to expand a runtime surface.
A1.10, post-2E.1, post-V1.2 and deeper ingest require separate approval in canonical documentation before implementation.

## A1.10 Memory Explorer: planned browser smoke matrix

| Scenario | Setup | Expected outcome |
| --- | --- | --- |
| Authorized provenance | Existing event in allowed room | Source references shown only from authorized response; no extra fetch |
| Wrong room | Same identifier queried from another room | Generic denial or not found; no source IDs or payload |
| Corrected event | Existing correction metadata | Supersession/correction visibly distinguished; original record unchanged |
| Empty change preview | Allowed room with zero changes | Stable empty state, no fabricated changes |
| Change-preview navigation | Authorized preview and detail | Stable link to existing read-only route; no mutation request |
| Untrusted text | Provenance string containing HTML markup | Rendered as text, never executable HTML |
| Missing context fields | Optional fields absent | Explicit unknown/absent state, no inferred values |
| Large result | More rows than bounded limit | Limit honored, deterministic ordering |
| Mobile viewport | 360px wide | Accessible labels and no horizontal clipping |
| Desktop viewport | 1280px wide | Selection and context visible without leaking other rooms |
| Network inspection | Exercise all interactions | No newly introduced POST/PUT/PATCH/DELETE calls |
| Audit integrity | Inspect existing logs before and after reads | No unintended writes by visualization |

Tests must exercise the **actual browser DOM** as well as API responses; unit tests alone are insufficient.
Never use synthetic permission fixtures to claim production authorization is verified.

## Genomics Lab: staged design (NOT approved for runtime)

1. **Raw intake quarantine**: encrypted-at-rest local storage, explicit consent, checksum, source format and room classification. No automatic public-room copy.
2. **Normalization**: immutable source bytes; versioned parser; reference genome build, chromosome naming and coordinate convention recorded; reject ambiguous builds.
3. **Annotation sandbox**: provenance for database version, transcript set, annotation method, and confidence; no diagnosis from unsupported variant evidence.
4. **Supervisor-gated summary**: separate authorization for raw variant access and derived summary export; redact identifiers by default.
5. **Validation**: malformed input, mixed genome builds, duplicate sample IDs, revoked access, parser crash, partial import and audit failure all fail closed.

No actual DNA data should be used in public CI. Use fabricated variants and synthetic files.

## Constitution Layer: change authority gate (NOT approved)

- Separate policy *proposal*, *review*, *approval* and *activation*; no self-approval by an agent.
- Immutable policy version and approver identity; rollback must preserve history.
- Live routing changes require explicit authorization and a deterministic dry run.
- Fail closed if approval record, room classification or audit write fails.
- No Constitution write endpoint or routing influence is implemented by this document.

## Art Lab: comparison and analysis gate (NOT approved)

- Define deterministic metric version and cross-version comparability before expanded comparison UX.
- Batch profiling must bound CPU/memory and enforce room-scoped asset access.
- OCR/embeddings must record model/version, source hash and extraction provenance; never silently index private image text.
- Drawing clusters are descriptive similarity groupings, not personality or medical conclusions.

## Deeper ingest gate (NOT approved)

- Model extraction as queued -> running -> completed/failed/interrupted, with append-only transitions.
- OCR/transcription outputs need provenance, bounded retries and explicit per-room indexing consent.
- Dedup must distinguish byte-identical content from near-duplicates; never silently delete a source.
- Validate crash recovery, idempotency, mixed classifications, denied access and audit rollback before activation.

## Approval checklist

- [ ] Canonical phase document names the exact new phase and scope.
- [ ] Human owner explicitly approves rights, routes, data classification and retention.
- [ ] Threat model and data-flow diagram reviewed.
- [ ] No regression in hypervisor, memory corrections, room isolation or audit.
- [ ] Automated tests and browser smoke tests pass on supported platforms.
- [ ] Operator rollback and failure-handling procedure documented.
- [ ] Only then may a separate runtime PR be opened.
