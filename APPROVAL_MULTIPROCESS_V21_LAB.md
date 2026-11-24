# KLONE – Approval Intent v2.1: file-backed multiprocessing laboratory

**Scope:** draft-only, laboratory-only; no external actions, no publication, and **no production database migration**. The test program uses a new temporary SQLite database and synthetic, in-memory HMAC signing keys. It does not contact the user's running KLONE services.

## Change

`EvidenceApprovalBridge(..., attach_existing=True)` registers the per-connection SQL receipt-verifier function and validates that the existing receipt table and five lab triggers are present **without running schema creation DDL**. This permits separate trusted processes to open the same previously initialized SQLite file. The default `attach_existing=False` retains existing fresh-DB behavior; never use that mode against an existing database or production database.

This is a **test-only connection protocol**, not an authentication boundary. A connection that can directly edit schema can still drop triggers; a database writer can also use SQL to change state directly when a valid evidence receipt is present. Even an ordinary `UPDATE state` may pass receipt checks while bypassing the actual actor authorization. The lab deliberately does not claim to fix either attack. A production design needs an isolated DB owner under independently enforced OS credentials with a narrow authenticated IPC API, no untrusted SQLite connections, and audited deny events.

## Tests

- `test_evidence_approval_bridge_attach.py` runs with only `klone.evidence_receipt` and `klone.evidence_approval_bridge` available: missing schema fails closed; second SQLite connection registers its own callback; a child **OS subprocess** opens its own connection and exercises the receipt + subject lock.
- `test_approval_intent_v2_multiprocess.py` needs the full KLONE approval modules: eight independently launched Python subprocesses each open their own file-backed SQLite connection and call the real `BoundDraftApprovalService` through `AtomicApprovalGateway` and Evidence Bridge. Expect exactly one approval event and one accepted signed intent, seven denied attempts. A second scenario commits revocation in one process and verifies that another process cannot approve afterward.

Both kinds of test share generated keys *with test processes only* through stdin pipes, which is not a production key isolation model. The tests avoid `multiprocessing.Queue` / `Event` because some Termux Python 3.13 builds lack the required `_multiprocessing` extension; readiness uses non-secret files in a temporary directory and OS subprocesses. They do not test an attacker with full filesystem write privileges or a durable trust-service boundary. Nor do they show that a signed assertion was issued by a real human.

## Manual test in a fresh Termux worktree

```sh
cd ~/klone-approval-intent-v21-lab
export PYTHONPATH="$PWD/src" PYTHONDONTWRITEBYTECODE=1
~/klone-next/.venv/bin/python -m unittest discover -s tests -p 'test_evidence_approval_bridge_attach.py' -v
~/klone-next/.venv/bin/python -m unittest discover -s tests -p 'test_approval_intent_v2_multiprocess.py' -v
```

Never point these tests at `~/klone/data/klone_mission_control.db` or any existing KLONE database. The tests generate their own SQLite files using `tempfile.TemporaryDirectory` and close them after use.
