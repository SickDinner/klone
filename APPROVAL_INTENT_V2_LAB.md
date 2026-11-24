# KLONE – Approval Intent v2 laboratory

This is **not** a production service or a security boundary against same-UID
local programs, direct SQLite writers or compromised signing keys.

## Motivation

A valid short-lived `SignedActorAssertion` authenticates an actor and role, not
the specific proposal or operation the actor intended. This experimental
wrapper requires a separate, short-lived signed intent for each *draft-only*
approval or revocation. The intent binds operation, actor, room, proposal ID,
version, content SHA-256, reason hash, nonce and a short expiry.

The intent signer must be a **separate trusted component** that authenticates
the actual user and checks authorization before signing. `make_intent_payload`
only constructs data to sign; it does not grant approval. Tests sign with
an ephemeral key in memory. No endpoint or token minting service is provided.

`BoundDraftApprovalService` validates request intent inside the same
`AtomicApprovalGateway._run` transaction (internal API), stores its replay
fingerprint atomically, and calls the existing `ApprovalAccess`. It refuses to
start without all three experimental Evidence Bridge v1.2 triggers. Evidence
validation itself remains in that bridge. It exposes no activation/publish
method. In-process lock serializes calls through the same SQLite connection,
**not across processes**.

## Limitations and threat model

- The underlying `AtomicApprovalGateway._run` method is internal; changes to
  that API require an integration test and review.
- SQLite schema validation is not a security boundary against privileged DB
  writers who can remove triggers, replace callbacks or directly UPDATE state.
- Python attributes are not access control. The writable gateway and SQLite
  connection must not be shared with untrusted components.
- True isolation requires an OS process running with distinct filesystem
  credentials / permissions or equivalently strong sandboxing. Termux worktrees
  under the same Android UID are **not** independent principals.
- Source authenticity, owner identity issuance, forensic attestation, durable
  audit on denied attempts, crash safety and multiprocess races remain pending.
- Denied attempts roll back the replay marker and journal event; record these
  attempts separately through a trusted ingress audit sink in a real service.
- Never deploy this alongside a production database or release authorization.

## Testing

```sh
cd ~/klone-approval-intent-v2-lab
PYTHONPATH="$PWD/src" ~/klone-next/.venv/bin/python -m unittest discover -s tests -p 'test_approval_intent_v2*.py' -v
```

The pure-intent tests run standalone. Separate integration tests with KLONE's
real `ApprovalJournal`, `AtomicApprovalGateway` and Evidence Bridge must run in
an isolated SQLite `:memory:` connection, before this prototype is merged.
