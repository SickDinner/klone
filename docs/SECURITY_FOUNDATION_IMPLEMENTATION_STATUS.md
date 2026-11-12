# Security foundation implementation status

This branch contains two **offline, pure Python policy primitives**, plus synthetic regression tests. No application routes, model clients, network transports, database writes, or privileges are added.

- `egress_policy.py`: manifest hashing, zone checks, same-room checks, explicit public-only allowlist gate, and final-byte hash verification helper. Defaults deny all external traffic. Personal data returns `require_approval` but **no approval integration exists**, so it must not be transmitted. Sensitive cognition and restricted bio are always denied by this initial prototype.
- `approval_policy.py`: immutable proposal transition validation. **Not an approval system**: it does not authenticate a human, persist proposals, check actual authorization, audit atomically or activate writes. `human_approved=True` is an input to be supplied only by a future authenticated service; do not expose it directly to untrusted callers.
- `tests/test_security_foundation_policy.py`: synthetic policy tests, no network.

Before any runtime wiring: validate destination provider identity, bind final serialized request bytes to manifest, enforce trusted classification at source, authenticate approval server-side, transactional persistence plus audit, replay protection, revocation and explicit phase approval. Current tests do not prove runtime safety.

## S1 containment integration in this branch

The existing clone-chat outbound Responses API transport in `dialogue.py` is explicitly blocked and its unguarded `urllib` implementation removed. The chat reply method now chooses bounded local rendering **before constructing any external prompt**, even if an API key is configured. A stored key is not a permission. This intentionally changes prior GPT-5.4 behavior: external rendering is unavailable until a separately approved, authenticated, classified transport is built. The key-configuration UI remains present but cannot activate egress.

This is a **targeted containment of the identified chat transport**, not proof that every possible outbound network sink in the entire repository has been inventoried. Before deployment, search and audit all HTTP clients and connectors. CI passing does not substitute for browser and runtime egress tests. No branch has been merged by this work.

## G1 preparatory sandbox: bounded VCF preflight

`genomics_preflight.py` provides a **pure, offline structural preflight** for small, uncompressed UTF-8 VCF byte strings. It requires a declared GRCh37/GRCh38 build, limits input to 8 MiB, each line to 1 MiB and variants to 100,000, and returns only counts and SHA-256. Tests use synthetic VCF records. It does **not** validate biological correctness, perform reference normalization, authenticate a caller, verify the declared reference against a reference genome, read FASTQ, annotate, persist or expose an intake endpoint. It is **not approved for real restricted-bio data** until the supervisor-gated intake and audit layer are implemented. Larger datasets will need a streaming, quota-enforced implementation.

## CI regression correction

The initial S1 containment run failed because two legacy clone-chat tests expected GPT-5.4 network rendering. Those tests now assert the intentional local-only behavior and the absence of outbound API calls. Await a complete green matrix before merge; never treat a single successful platform as complete verification.

## I1 bounded ingest fingerprint prototype

`ingest_fingerprint.py` reads binary streams in at most 64 KiB chunks, enforces a 512 MiB absolute object cap (lower per-call limits supported), and emits SHA-256/size/chunk count without retaining file contents. `plan_ingest` makes a read-only duplicate/candidate decision using a caller-supplied hash set. **The caller must derive that set from the authorized room only**. This is not a persistent index, resumable ingestion pipeline, authorization service, OCR, transcription, or vectorization. All associated tests use synthetic bytes.

## S2 offline SQLite approval journal

`approval_journal.py` adds an isolated SQLite-backed proposal/event journal with `BEGIN IMMEDIATE` transactional transitions and audit-event inserts in the same transaction. It is **not wired into the application's repository or public API** and cannot mutate Constitution parameters. The journal is deliberately append-only for events but the database is not tamper-evident against a privileged SQLite administrator. A caller-supplied `human_approved=True` is **not trustworthy authentication**: a future authenticated service must derive this server-side from verified human identity, capability and room policy. The current prototype does not enforce time expiry, roles, policy revocation, cryptographic signatures, audit log immutability or crash recovery beyond SQLite transactions. Never expose this object directly to an LLM or network client.

## S2 offline approval access prototype

`approval_access.py` adds a deny-by-default **offline adapter** for caller-verified actor identity, room isolation, owner-only human approval and timezone-aware expiry checks. Seven synthetic tests cover the permitted path and denial cases. **This is not an identity provider**: the `authenticated` field is caller-supplied and must never be accepted from a client, agent or model. The deadline map is in-memory and is lost on restart; absent expiry denies activation. No real mutation, external egress, Constitution write, public route or service registration is enabled. Production activation requires durable deadline storage, authenticated session provenance, revocation and atomic audit policy enforcement.

## S2 durable expiry upgrade

Approval proposal creation now optionally stores its timezone-aware expiry in the isolated SQLite journal within the same transaction as proposal and initial audit event. The access adapter reads expiry from SQLite, not its bootstrap dictionary; creating a new adapter does not discard an existing deadline. The journal still has **no real identity attestation**, no authenticated API, no automatic expiry sweep, and no target mutation. The `expires_at` dictionary is only a bootstrap input for creating new proposals. The earlier description of volatile-only deadlines is superseded by this section.

## S2 signed actor assertion verification

`approval_identity.py` now verifies short-lived HMAC-SHA256 actor assertions using a server-injected secret of at least 32 bytes. It checks signature in constant time, room, role, identity, issued-at and a maximum five-minute lifetime; it then constructs the `VerifiedActor` context used by the offline access adapter. This **does not authenticate a human by itself**: only an independently authenticated, trusted server issuer may mint these assertions. There is currently no issuer, API middleware, session binding, token revocation, nonce replay registry, key rotation or production secret management. Never expose a signing key to a client or model. Tests use a synthetic fixed secret. No mutation activation is wired.

## S2 revocation and offline gateway

`approval_journal.py` now records permanent proposal revocations in a dedicated table, together with an audit event in the same SQLite transaction. `approval_access.py` denies transitions for revoked proposals and restricts revocation to a same-room owner role. `approval_gateway.py` composes signed-assertion verification, one-use replay guard, role/room access and approval journal. Synthetic integration tests exercise signed proposal, validation, independent owner approval, revocation and denied activation. This is still **offline only**: a trusted login/session issuer, signing-key lifecycle, atomic replay-consumption plus approval transition across connections, real-world identity binding, and target mutation authorization remain missing. In particular, an assertion is consumed before a rejected transition, which is intentionally fail-closed but not a fully atomic business transaction. Do not expose gateway to untrusted callers or enable writes.

## S2 key rotation verification

`approval_keyring.py` adds a bounded, offline verification keyring supporting up to eight independently identified HMAC signing keys, overlapping verification windows and hard expiry. It does not mint assertions or fetch keys. Synthetic tests cover overlapping old/new keys, wrong key, unknown key, expired key and duplicate key IDs. This is a **standalone verifier**, not yet wired into `ApprovalGateway`. The gateway continues using a single injected secret. Production requires a trusted authentication issuer, session binding, revocation, key custody, and a single atomic replay-and-approval transaction. The existing SQLite replay guard consumes a token before the journal transition; a rejected transition therefore consumes its assertion. No Constitution write or external egress is enabled.

## S2 atomic offline gateway experiment

`approval_atomic_gateway.py` composes keyring verification and replay marker insertion with approval journal writes under one SQLite `BEGIN IMMEDIATE` transaction. Journal write methods use SAVEPOINT when invoked inside that transaction, and ordinary BEGIN/COMMIT otherwise. Synthetic tests cover atomic creation, duplicate assertion rejection, rollback after failed transition, and revocation. This requires **one shared SQLite connection** and does not establish safety across distinct databases, distributed processes, external side effects or real Constitution writes. The original `ApprovalGateway` remains available as a legacy offline prototype and is not atomic. No trusted issuer or authenticated API exists. This experiment requires successful CI and security review before any production integration.
