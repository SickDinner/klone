# KLONE research approval: security boundary and integration checklist

Status: design contract, **not an implemented authenticated approval API**.

## Assets and adversaries

Protected assets: source-backed public research reports, immutable claim revisions,
audit records, Hypervisor policy state, and private/sealed room data. Threats
include malicious clients, compromised research agents, stale grants, forged
request headers, replayed proposals, tampered SQLite files, and concurrent
policy changes. Local administrator compromise is outside the guarantees of
ordinary SQLite hashing.

## Mandatory privileged flow

1. Authenticate the human/service through a real session mechanism. Never
   trust `X-Klone-Principal`, `X-Klone-Role`, or a client-supplied `verified` flag.
2. Authorize `research.claim.commit` on the **exact** public report
   `trace_id` and version, with current Hypervisor policy and room
   classification. Deny by default.
3. Load the stored report; verify its digest, room classification, and that
   every claim source reference belongs to the report.
4. Recompute proposal and review-bundle fingerprints. Recheck reviewer identity
   and the human decision, including rationale and explicit approval.
5. Bind decision, session identity, grant/policy version, report digest and
   proposal ID into a server-side transaction request. Never accept a boolean
   `authorized` from HTTP or a research agent.
6. Within a single transaction, check current policy epoch and report digest
   against the expected values, enforce replay/idempotency constraints, append
   the claim and append the audit event. Roll back **both** on any failure.
7. Return an auditable receipt; expose separate integrity verification and
   reconciliation for missing/corrupt audit entries.

## Existing pieces and limitations

- `research_proposals.py`: proposal content hashing and source membership.
- `research_review_bundle.py`: deterministic evidence review handoff.
- `research_approval_gate.py`: read-only preflight; trusted reviewer objects
  can be forged by callers and are **not** proof of identity.
- PR #34 `research_atomic_ledger.py`: experimental separate SQLite atomic
  claim/audit store. Its `authorized` flag is not authorization; no
  Hypervisor integration or report validation in its transaction.
- PR #35 `research_boundary_contract.py`: pure session/grant binding. Its
  `verified` flags are not cryptographic capabilities.
- `request_context.py`: reads caller-supplied HTTP headers and MUST NOT be
  used as an authenticator.
- Existing `research_evidence.py` is a different ledger. No migration or
  replacement is implied by the experimental atomic store.

## Required adversarial regression tests before activation

- Forged headers and `verified=True` assertions do not grant writes.
- Session revocation, stale policy epoch, room reclassification and grant
  version mismatch deny writes, including during concurrent requests.
- Source reference not present in the exact report version denies writes.
- Replay, duplicate proposal, concurrent revision updates and audit failure
  cannot create orphaned records.
- Database write interruption, crash recovery, audit corruption and missing
  records are detected; no false claim of tamper-proof storage.
- Private/sealed room content never enters public evidence or logs.
- Read-only preview endpoints cannot reach the privileged commit function.

## Next engineering step

Implement a server-owned authenticated session and Hypervisor grant resolver,
then a single privileged service with a transaction-time policy check and
audited persistence. Keep the API disabled until the full adversarial suite
passes on Linux, Windows and Android/Termux where supported.
