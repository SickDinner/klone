# Hypervisor 2C deployment gate

Status: **experimental, disabled for untrusted workloads**.

## Verified implementation
- Room/role/classification policy checked before read delegation.
- Audit callbacks must succeed before executing a handler.
- Output policy checked before and after the read; JSON output byte cap.
- Explicit worker registry, fixed argv, no shell, POSIX process group termination on timeout.
- No public worker API route is exposed.

## Must complete before production
1. Implement and test Windows Job Object kill-on-close and descendant termination; do not enable Windows workers before then.
2. Enforce OS-level CPU/memory quotas and restricted identities or containers. POSIX process groups are not a sandbox.
3. Enforce maximum request concurrency and per-worker quotas; avoid unbounded worker spawning.
4. Validate real SQLite-backed audit persistence, transaction behavior, failures and unknown-room denial events.
5. Review output classification and verify no private data leaks via logs, stderr, exception strings or worker output.
6. Add real API authentication, authorization, trace correlation and end-to-end tests before exposing any endpoint.
7. Verify GitHub Actions on supported operating systems and both Python versions.
8. Review base/main ancestry and stacked PRs. Do not assume squash merges to feature branches updated main.

## Fail-closed contract
Unknown rooms, unregistered seams, classification mismatches, audit failures, malformed JSON, oversized outputs, worker failures and timeouts must not yield data to the caller.

## Scope
This document does not certify the system as secure or production ready.
