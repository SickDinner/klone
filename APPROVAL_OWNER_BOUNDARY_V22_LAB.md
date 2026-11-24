# KLONE Approval Owner Boundary v2.2 – fail-closed research prototype

**Status: LAB ONLY. Not a deployable approval server; no database mutations.**

## Confirmed finding on PR #190

`test_evidence_approval_bridge_attach.py` demonstrates that a second process can
run a raw SQL `UPDATE approval_proposals SET state='approved'` when a valid receipt
already exists, without running the signed actor/intention approval gateway. The
receipt verifies the draft evidence, not *who* authorized the transition.
The attack works in the original lab DB because the SQLite trigger does not
require `SignedActorAssertion` or `SignedDraftIntent`.

This is a **known authorization bypass** for writers that can open the DB, not
proof of production compromise (this module is not deployed). Other database
privileges like DROP TRIGGER are also available to a same-UID writer.

## Design rule

To move toward a trustworthy service, the DB and its WAL/SHM sidecars should be
owned by a **separately sandboxed OS principal**, not simply another Python
process. All approval attempts must enter through a trusted IPC gateway with:

1. Kernel-verified caller identity and an explicit allowlist (Android UID/package
   verification through a platform service, or equivalent OS isolation).
2. Authentication, role + room policy, and a signed intent bound to the precise
   draft, version, operation, nonce, and expiry.
3. Transactional receipt verification, per-intent replay prevention, revocation
   checks, and durable audit for denied as well as allowed attempts.
4. Private database + secrets + journal sidecars (no direct DB path to callers),
   safe descriptor-relative file opening and protections against path races.
5. No activation/publication APIs until separately authorized and reviewed.

## This change

`approval_owner_boundary_v22.py` provides **only fail-closed preflight**:
- AF_UNIX `SO_PEERCRED` UID must differ from the service's actual `geteuid()`.
- The existing absolute-path database must be a service-owned 0600-like file
  under a service-owned 0700-like immediate parent; symlinks are rejected.
- Any unsupported platform or missing credentials denies, with no silent
  fallback to unverified JSON identity.
- **Termux's same-UID clients are denied, even when the DB file is mode 0600**.
- No secrets, endpoints, approval actions, file writes or socket listener.

The positive foreign-UID test uses mocking. It does **not** prove that a
separate Android app or other UID service has been installed or can connect.
`lstat()` is TOCTOU-sensitive; a real service must use safe fd-based opening,
check WAL/SHM path ownership, and hold verified inodes. The preflight does not
check a caller allowlist, package signature, or session identity, so passing it
is never sufficient to grant an approval.

## Regression

`PYTHONPATH=src python -m unittest discover -s tests -p 'test_approval_owner_boundary_v22.py' -v`

Keep PRs #188 → #189 → #190 unmerged until independently reviewed. This module
should be developed on a new stacked **draft PR** and not wired into production.
