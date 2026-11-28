# KLONE v3.7 — synthetic memory evidence contract

Status: experimental, test-only. No production integration.

The goal is to evaluate whether explicitly human-labeled synthetic review records distinguish current support, stale evidence, uncertainty and room-boundary violations. The evaluator rejects incomplete, duplicate, extra and invalid case records. It does not infer truth, validate real access control or access memory.

## Run

```sh
python -m unittest discover -s tests -p test_memory_evidence_contract_v37.py -v
```

Six synthetic scenarios: current, superseded, deleted, missing, conflicting, wrong room. Ten unit tests cover the scoring contract itself. No dependencies beyond Python standard library, no model calls, network, database access or writes to user memory.

## Research leads

- Memora (https://arxiv.org/abs/2604.20006): forgetting-aware evaluation.
- PACMI (https://arxiv.org/abs/2610.05732): provenance-aware invalidation research.
- NIST AI Agent Standards Initiative (https://www.nist.gov/super-intelligence/si-agent-standards-initiative): security and interoperability context.

These are research leads, not a reproduction of the papers or a claim of verified effectiveness.

## Next acceptance gate

A separately reviewed integration test must obtain observed labels from actual read-only application outputs using entirely synthetic fixtures. Test real room isolation and correction handling, not only the scoring helper. Report failures independently by class; do not treat abstention as universally correct. Keep human approval and existing guards unchanged. The v3.6 verification gate and the full regression suite remain independent prerequisites.

No live data, new APIs, background jobs, autonomous actions or production behavior changes are in scope.
