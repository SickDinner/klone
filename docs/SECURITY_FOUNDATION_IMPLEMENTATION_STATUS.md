# Security foundation implementation status

This branch contains two **offline, pure Python policy primitives**, plus synthetic regression tests. No application routes, model clients, network transports, database writes, or privileges are added.

- `egress_policy.py`: manifest hashing, zone checks, same-room checks, explicit public-only allowlist gate, and final-byte hash verification helper. Defaults deny all external traffic. Personal data returns `require_approval` but **no approval integration exists**, so it must not be transmitted. Sensitive cognition and restricted bio are always denied by this initial prototype.
- `approval_policy.py`: immutable proposal transition validation. **Not an approval system**: it does not authenticate a human, persist proposals, check actual authorization, audit atomically or activate writes. `human_approved=True` is an input to be supplied only by a future authenticated service; do not expose it directly to untrusted callers.
- `tests/test_security_foundation_policy.py`: synthetic policy tests, no network.

Before any runtime wiring: validate destination provider identity, bind final serialized request bytes to manifest, enforce trusted classification at source, authenticate approval server-side, transactional persistence plus audit, replay protection, revocation and explicit phase approval. Current tests do not prove runtime safety.

## S1 containment integration in this branch

The existing clone-chat outbound Responses API transport in `dialogue.py` is explicitly blocked and its unguarded `urllib` implementation removed. The chat reply method now chooses bounded local rendering **before constructing any external prompt**, even if an API key is configured. A stored key is not a permission. This intentionally changes prior GPT-5.4 behavior: external rendering is unavailable until a separately approved, authenticated, classified transport is built. The key-configuration UI remains present but cannot activate egress.

This is a **targeted containment of the identified chat transport**, not proof that every possible outbound network sink in the entire repository has been inventoried. Before deployment, search and audit all HTTP clients and connectors. CI passing does not substitute for browser and runtime egress tests. No branch has been merged by this work.
