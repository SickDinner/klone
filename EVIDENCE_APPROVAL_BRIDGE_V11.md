# KLONE Evidence Approval Bridge v1.1 (laboratory-only)

This addon depends on the user's already-tested `src/klone/evidence_receipt.py` from Evidence Receipt v1.0. It adds a connection-scoped SQLite trigger that verifies a signed receipt **at the moment the `ApprovalJournal` state is changed to `approved`**. It binds the receipt to the proposal, exact draft text digest (`ApprovalProposal.patch_sha256` is defined as the SHA-256 of the UTF-8 draft text in this lab), target version, public room, source-card IDs, dossier hash and debate hash. An `activating` or `active` state is always denied in this laboratory.

Crucial trust assumption: the injected `trusted_provider(proposal_id)` must reload *current trustworthy evidence inputs*, not accept model-generated or HTTP request fields. The HMAC key must be stored only by a trusted service. The laboratory tests use generated keys and synthetic roles.

The SQL callback checks source reports using their **self-consistency hash**, not a trusted publisher signature. It does not establish independent research evidence or validate claims. It does not establish user identity; `AtomicApprovalGateway` checks separately generated lab assertions in device tests. SQLite triggers are not a security boundary against a writer who can alter the schema or replace the connection's registered functions. A file-source TOCTOU race, key compromise, multiple processes, database tampering, provenance verification, production migration and release authorization all remain out of scope.

The package **must not be installed into a production database or deployed**. `EvidenceApprovalBridge.__init__` writes lab-only DDL to its supplied SQLite connection. The tests create a fresh `sqlite3.connect(':memory:', isolation_level=None)` for each case.

## Files

- `src/klone/evidence_approval_bridge.py`: experimental adapter (no network or filesystem writes).
- `tests/test_evidence_approval_bridge_sqlite.py`: 12 SQLite boundary tests, runnable with v1.0 receipt module.
- `tests/test_evidence_approval_bridge_gateway.py`: 6 tests with KLONE's real `ApprovalJournal` and `AtomicApprovalGateway` (run in Termux).

## Run on Android Termux from `~/klone-evidence-receipt-v1`

```sh
export PYTHONPATH="$PWD/src" PYTHONDONTWRITEBYTECODE=1
~/klone-next/.venv/bin/python -m unittest discover -s tests -p 'test_evidence_approval_bridge*.py' -v
~/klone-next/.venv/bin/python -m unittest discover -s tests -p 'test_evidence_receipt*.py' -v
```

Expected: **18 new tests** (12 SQLite + 6 real approval gateway), plus the existing **21 receipt tests**, if local files and code are as expected. The 6 integration tests are not claimed as completed until run in the user's KLONE environment.
