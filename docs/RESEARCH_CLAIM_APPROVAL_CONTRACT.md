# KLONE 3B.7: Claim proposal approval contract (design only)

The research agent can prepare an immutable, deterministic `ClaimProposal`. This proposal is **not** an approval, authorization token or proof that a source supports a statement.

## Proposed service boundary

1. Authenticate the human or trusted service identity. Never accept a caller-supplied `actor_role` as proof of authority.
2. Verify the exact proposal digest, trace ID, report version and all source references against the integrity-checked public report.
3. Require an explicit authorization path for public evidence writes. `public-room` currently has `propose` but not `write`. Do not elevate it implicitly.
4. Reject a duplicate or stale approval and ensure the approved content is byte-for-byte the reviewed proposal.
5. Commit the claim revision and audit record atomically in one SQLite transaction (or durable outbox), failing closed on any audit error.
6. Include proposal ID, report trace/version, claim ID, revision, actor identity, decision and result in the audit event. Do not log raw sensitive documents.
7. Preserve rejection attempts in audit where policy and classification allow it; never claim an unaudited denial was recorded.
8. Test tampering, replay, stale proposal, unauthorized role, missing report, audit failure rollback, concurrent approval, and Windows database handles.

## Current status

No approval endpoint, approval token, persistent proposal queue or write seam is implemented. This document is an implementation contract, not a claim of completed enforcement.
