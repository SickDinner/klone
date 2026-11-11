# KLONE 3B.6 evidence ledger: deployment gate

Status: experimental, not authorized for production or automatic agent writes.

## Current guarantees

- A claim has append-only revisions with explicit review labels and source references.
- `append_from_report` verifies that supplied references occur in an integrity-checked, stored public report.
- The exact report trace and version are persisted with the claim revision.
- The SHA-256 digest covers claim text, review label, references, report trace and report version.
- The ledger does **not** verify that the cited source supports the claim, nor prove that the database was not replaced.

## Required before workflow integration

1. **Permission model:** `public-room` currently permits `propose` but not `write`. Do not silently grant write access or treat a `read` decision as write authorization. Introduce a reviewed proposal/approval mechanism or an explicitly authorized service seam.
2. **Durable audit:** authorize and audit every attempted claim mutation, including denied, delegated, completed and failed outcomes. Prefer a shared transaction for claim write and audit, or an outbox with recovery, to prevent unaudited successful writes.
3. **Identity:** authenticate the caller and bind actor, room, classification, report trace/version and claim revision to audit metadata without exposing sensitive content.
4. **Isolation:** allow only trusted local paths and public citations. Do not expose direct ledger writes via the developer HTTP preview.
5. **Schema and migrations:** formalize migrations before any existing deployment upgrades; the experimental table is currently created on first use.
6. **Threat model:** SHA-256 detects incidental corruption, not malicious rewrites by an attacker who can modify both data and digest.

Until these are implemented, treat `EvidenceLedger` as an internal data model and do not wire it into the live research workflow.
