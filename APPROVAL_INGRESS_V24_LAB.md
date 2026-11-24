# KLONE Approval Ingress v2.4 — bounded intake + denial audit (LAB ONLY)

**Non-production.** This PR does **not** start a listener, grant approvals, revoke approvals, publish results, create a credential authority, isolate an Android app UID, or connect to the real KLONE approval database.

## Why this exists

v2.1 established separate-process SQLite concurrency. v2.2 confirmed that a Termux same-UID subprocess is **not** an isolation boundary. v2.3 introduced descriptor-anchored DB and WAL/SHM inspection, but the inspected file descriptors do not bind Python `sqlite3.connect(path)` or stop same-UID direct writes. This v2.4 component studies the *next boundary*: which requests may reach a **future** privileged owner process, and how to account for rejected attempts.

## Mechanism

`screen_draft_envelope(connected_unix_socket, raw_bytes, ledger, trusted_allowlist)`:

1. Reads `SO_PEERCRED` via existing `kernel_peer_uid`, not from a claimed JSON actor/UID.
2. Denies any request from the service's own effective UID. The peer must be on a distinct UID **and** an exact trusted UID allowlist. Unsupported OS/transport or missing credentials deny.
3. Requires bounded (1–4096-byte), strictly parsed UTF-8 JSON with exactly `domain`, `action`, `request_id`, `draft_sha256`. Domain is `klone-ingress-v24-lab`; the **only** action is `submit_for_verification`. Duplicate JSON keys, extra claims, wrong action, invalid IDs and digests deny. No actor identity is accepted from this envelope.
4. Within `BEGIN IMMEDIATE`, enforces one-use `request_id` and appends an audit event. An existing request ID produces a separate **denied** event. Denied requests are logged too, without the raw bytes. A failed audit transaction never returns a screened result.
5. Chains audit rows by domain-separated HMAC-SHA256 tags; detects edited earlier rows, missing prefix rows and inconsistent sequence numbers during subsequent intake. It is **not** independent tamper evidence: an owner with DB/key access can rewrite the log or truncate its tail. External signed checkpoints are required to detect tail truncation.

`ScreenedEnvelope` is **not** an authorization token, proof of a person, a signed intent, or a capability. It contains only the digest of the screened bytes and the kernel peer UID. The ingress intentionally cannot call any approval/publish API.

## Important limits

- The real distinct-UID success case has **NOT** been exercised: positive tests use mocked credentials. A real socket test verifies same-UID rejection on Linux/Android. On Windows only the portable logic runs; the real socket test skips.
- Android `SO_PEERCRED` authenticates an OS UID, **not** a human, application package signature, or a specific permission. Allowlist membership alone cannot authorize a sensitive action. Future platform integration must verify the owning app/signature or Android Binder identity, and then authenticate the actor and signed v2 intent against current DB state.
- This file creates **no listening socket** and contains **no wire framing, TLS, request timeout or flood protection**. Input length is bounded **only after bytes have been delivered**; a future listener must impose framing, timeouts, concurrent connection limits and backpressure before read.
- The local lab SQLite audit database does not have independent owner protection, append-only WORM semantics, or external checkpointing. Secrets reside only in caller memory in this experiment. A same-UID writer may bypass the check or directly modify SQLite tables.
- Denials are recorded only if audit storage/clock remains healthy. On audit write failure the request fails closed, **but it is impossible to promise that the failed attempt was durably logged**.
- The test schema must be initialized explicitly in an isolated database. `V24AuditLedger` does not silently alter an existing DB. This is separate from all production approval tables and from any trusted evidence receipt.
- Audit verification on every attempt currently scans the local audit chain (O(number of events)); efficient checkpoints and retention are future work, with independent anchoring necessary to avoid weakening tamper detection.

## Evidence and regression

Local Linux lab `python -m unittest discover -s tests -p test_approval_ingress_v24.py -v`:

**23 tests passed** including real same-UID Unix socket denial, malformed/duplicate JSON, forged UID claim, replay, concurrent competing requests on separate SQLite connections, audit tampering, audit rollback on write errors, lost credentials, safe digest-only logging, and explicit demonstration that truncating the audit tail can evade a purely local HMAC chain.

No production DB or shared KLONE service is touched. Full stacked-repo CI and Termux focused/full regression are required before marking this stage verified.

## Next security gates

1. Independent OS identity and protected DB/key storage under a distinct Android app UID (or equivalent, e.g. reviewed Binder-based service), with real cross-UID negative and positive tests.
2. Bounded authenticated IPC with peer identity *and* actor identity, signed draft intent v2, evidence receipt and current proposal binding, all revalidated transactionally.
3. Durable independently anchored audit checkpoints and denial-audit observability without exposing secrets.
4. Multiprocess crash/restart/race tests, denial-of-service limits, deterministic replay evidence, regression CI and expert threat-model review.

Until these gates pass, keep this **stacked draft PR** unmerged and disconnected from production.
