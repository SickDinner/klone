# Security Foundation S1/S2: Egress Guard and Write Approval

Status: **design proposal only**. No authorization for new runtime endpoints, external model traffic, Constitution writes, raw genomic intake, OCR or transcription.

## Scope and threat model

Protected zones: public knowledge, personal knowledge, sensitive cognition, restricted bio. The room hypervisor remains authoritative. Attackers may control imported messages, documents, OCR text, tool outputs, model responses or malformed API requests. Threats include prompt injection, cross-room retrieval, accidental external disclosure, approval forgery, stale grants, audit gaps, data retention beyond policy, and oversized batch denial of service.

Trust boundaries:
1. Import -> quarantined source with immutable checksum and classification.
2. Storage/search -> room-scoped retrieval with least-privilege checks.
3. Context assembler -> full outbound prompt and tool argument construction.
4. Egress Guard -> external model transport; **all** payload segments are classified.
5. Model output -> untrusted text, not an instruction or authorization.
6. Proposed writes -> human approval -> transactional activation -> append-only audit.

## S1: Egress Guard contract

A request must include: `request_id`, `principal`, `actor_role`, `room_id`, `destination_provider`, `destination_model`, `purpose`, `payload_manifest` (hash, byte length, source refs, classification for each prompt/system/tool/file segment), `policy_version`, and optional `grant_id`.

Decision: `allow | deny | require_approval`, machine-readable reason code, effective scope, expiry, policy hash, audit correlation ID. No raw sensitive payload in denial logs.

Default matrix:

| Zone | Local inference | External inference |
| --- | --- | --- |
| public knowledge | allowed by room policy | only if provider allowlisted and purpose authorized |
| personal knowledge | room-scoped | deny unless explicit scoped approval |
| sensitive cognition | room-scoped | deny by default; exceptional approval must be explicit |
| restricted bio | room-scoped and restricted role | deny by default; exceptional approval must be explicit |

A configured API key **never** constitutes approval. A system prompt, retrieved memory, OCR extract, tool result, filename or error context must be classified before outbound serialization. Deny when classification, policy, audit, or destination identity is unavailable. Recheck the finalized serialized request immediately before network transmission; reject post-approval payload changes. External API error reporting must not echo private prompts.

Acceptance tests: public approved call; missing key; present key but no grant; mixed public/bio payload; indirect prompt injection in imported content; mismatched room; expired/revoked grant; provider/model mismatch; changed payload hash; audit write failure; retries without duplicated egress; streaming chunks; redacted logs. Test with a mock provider, no real personal data.

## S2: Write-Approval state machine

States: `proposed -> validated -> awaiting_approval -> approved -> activating -> active`. Terminal alternatives: `rejected`, `expired`, `failed`, `rolled_back`. Illegal transitions fail closed.

Proposal: immutable `proposal_id`, proposer, target room/object, exact patch and precondition version, canonical patch hash, justification, requested capability, expiry, policy version. Validation is read-only. Approval binds human identity, authenticated session, exact patch hash, scope and expiry. Proposer cannot self-approve; an agent cannot impersonate a human approver. Activation checks all preconditions and reauthorizes at commit time. Atomic mutation plus audit or no mutation. Replay of the same approval is idempotent, not a second write. Rollback is a new audited version, never deletion of history.

Initial implementation should be Constitution parameter changes only, behind an explicit feature gate. Memory corrections and other write surfaces require separate contracts and approvals.

Acceptance tests: valid proposal, changed patch after approval, stale target version, cross-room write, insufficient role, approval replay, expired approval, concurrent approvals, audit outage, activation crash/recovery, rollback and emergency disable.

## S3-S6: downstream boundaries

- Genomics: VCF-first quarantine and synthetic fixture tests; reference build recorded; no unrestricted FASTQ execution; never export raw variants via search.
- Ingest: streaming parser, bounded memory, SQLite indexes, checkpoints and idempotent recovery before embeddings.
- OCR/transcription: explicit opt-in, versioned extractor, provenance and classification inheritance; embeddings remain room-scoped and revocable.
- FASTQ: separate resource budget, reference pipeline version, checksums and supervisor approval.

## Delivery and ownership

1. Review current model routing and outbound HTTP call sites; inventory every network sink.
2. Review current permission checks, room classification and audit transaction semantics.
3. Add **tests with mocked network** for all denial and mutation cases before enabling either surface.
4. Land S1 in deny-by-default mode with no external traffic enabled.
5. Seek a **separate canonical phase approval** for activating external egress or Constitution writes.
6. Stage S2 behind disabled feature flag; review and test on supported platforms.
7. Never treat this document or a GitHub merge as production permission.

### Security invariants

- No implicit privilege escalation by a model or plugin.
- No secret-bearing payloads in audit or CI artifacts.
- Classification propagates through transformations and summaries.
- All decisions are versioned, reproducible, and traceable.
- Revocation blocks future actions; previous history remains immutable.
