# KLONE v3.5 — signed service identity and audit receipt verifier (LAB)

## What it verifies

The verifier accepts a narrowly defined receipt signed with Ed25519 by an
observer whose public key is supplied through a trusted, out-of-band key ring.
The service identity claim is bound to a fresh caller nonce, a service ID, a
40-character application commit, a local loopback listener, a process ID and
start-time token, owner UID, executable and command digests, and observer ID.
The audit receipt binds an event to the exact verified identity receipt.
Ordered audit events form a SHA-256-linked sequence, and every event signature
is checked independently.

## Trust limits

- A valid signature authenticates the trusted observer's statement. It does
  not independently read `/proc`, confirm that a PID is alive, or prove that
  the observer correctly measured the process.
- The verifier does not create keys or receipts, discover ports, make network
  requests, read files, access SQLite, start or stop services, or grant rights.
- A receipt digest is an integrity identifier, not an authenticity proof.
- Callers must generate unpredictable nonces, keep the public-key registry
  under trusted configuration, rotate/revoke keys operationally, and define
  retention for audit material.
- The existing v3.2/v3.4 local health probe remains unauthenticated unless a
  caller explicitly verifies a receipt with this API. HTTP 200 alone is not
  identity evidence.

## Suggested integration contract

The trusted local observer should gather OS process data independently, sign
only after checking the live listener owner, and return a short-lived receipt.
The API server or operator then verifies it with the exact expected nonce,
service ID, commit, and trusted key ring. Only after that result is verified
should a downstream audit event cite the identity receipt digest. This module
does not perform that privileged collection and must not be wired to a
production authorization or process-control path without separate review.

All tests use synthetic keys and data. No private key or production evidence
is included in this change.
