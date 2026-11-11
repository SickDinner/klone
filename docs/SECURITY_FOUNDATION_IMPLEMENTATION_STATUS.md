# Security foundation implementation status

This branch contains two **offline, pure Python policy primitives**, plus synthetic regression tests. No application routes, model clients, network transports, database writes, or privileges are added.

- `egress_policy.py`: manifest hashing, zone checks, same-room checks, explicit public-only allowlist gate, and final-byte hash verification helper. Defaults deny all external traffic. Personal data returns `require_approval` but **no approval integration exists**, so it must not be transmitted. Sensitive cognition and restricted bio are always denied by this initial prototype.
- `approval_policy.py`: immutable proposal transition validation. **Not an approval system**: it does not authenticate a human, persist proposals, check actual authorization, audit atomically or activate writes. `human_approved=True` is an input to be supplied only by a future authenticated service; do not expose it directly to untrusted callers.
- `tests/test_security_foundation_policy.py`: synthetic policy tests, no network.

Before any runtime wiring: validate destination provider identity, bind final serialized request bytes to manifest, enforce trusted classification at source, authenticate approval server-side, transactional persistence plus audit, replay protection, revocation and explicit phase approval. Current tests do not prove runtime safety.
