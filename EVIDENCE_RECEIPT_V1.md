# KLONE Evidence Receipt v1.0 (proposed module)

This is a **draft-only**, side-effect-free receipt library. It is **not production-integrated** and does not issue credentials, verify user identity, authenticate publication sources, or authorize external actions.

A trusted issuer must validate caller identity and Hypervisor policy, provision the HMAC secret securely, then call `make_subject` with the verified inputs and sign it. A verifier must **rebuild the expected subject from current verified input** before calling `verify`. Do not trust an `expected_subject` supplied by an untrusted caller.

Signature indicates that a key-holder signed the subject. It does **not** establish that the evidence is scientifically sound or that the works are independent. `independent_sources_verified` and `scientific_claim_verified` are always `False`.

## Install into a separate worktree

From `~/klone-council72-cross-review`, create a detached worktree and copy the ZIP's `src/` and `tests/` files to it. **Do not overwrite** any existing file.

Example test command:

```sh
cd ~/klone-evidence-receipt-v1
PYTHONPATH="$PWD/src" PYTHONDONTWRITEBYTECODE=1 \
  ~/klone-next/.venv/bin/python -m unittest discover -s tests -p 'test_evidence_receipt*.py' -v
```

The local E11 integration test skips if that specific report pair is not present.

Production requirements still outstanding: independent authentication of the evidence issuer, HSM/secret management, a trusted policy-integrated signer, real source provenance, atomic receipt verification in the approval gateway, persistence durability, cross-process/concurrency tests, and release authorization separated from draft approval.
