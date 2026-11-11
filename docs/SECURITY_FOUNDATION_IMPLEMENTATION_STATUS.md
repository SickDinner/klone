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
