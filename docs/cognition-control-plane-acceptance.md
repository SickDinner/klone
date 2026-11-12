# KLONE integration acceptance scope

`tests/test_cognition_control_plane_evidence_e2e.py` exercises a bounded,
deterministic integration path:

1. Simulate eight cognition steps and verify deterministic replay.
2. Route a synthetic memory-shaped read through Hypervisor policy.
3. Require prehandler audit and output authorization.
4. Verify trace ID, digest and completed audit events.
5. Append a normalized synthetic CI observation to isolated SQLite test evidence.
6. Confirm the dashboard sees the observation but does not approve the run.
7. Assert restricted classification and audit failure prevent handler execution.

**Limitations:** the memory handler is synthetic, the audit callback is in
memory, and the evidence record is a test fixture. This is a cross-module
integration regression, not a real Android execution or a production
end-to-end acceptance of persistent Memory Core and durable audit.

Follow-up: wire a read-only real Memory Core facade with explicit room
authorization, test a temporary persistent audit store, and separately
verify GitHub/Termux provenance before accepting deployment.
