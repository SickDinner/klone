# Research history and creative measurement review v6.6–v6.9

Baseline: aaa2e7ace0b2ce8719be55cbeb7dadf7bfc555f9.
Owner-reported Android regression: 1147 passed, 323 subtests, 1 Windows skip, 1 Starlette/AnyIO warning.

## v6.6: local research history
Explicit bounded JSON input, at most 100 observations, parsed using the existing summary parser. Static HTML and JSON output. Missing observations are not zero, and the input order is not verified chronology. The output never upgrades supplied results to independent attestations or claims CI verification.

## v6.7: existing memory test inventory (documentation only)
Reviewed test names at the baseline: test_memory_integration_v38_v39.py has 12 methods, covering room scoping, cross-room replacement rejection, missing provenance abstention, correction state and persistence. test_provenance_privacy_v40.py has 8 methods, covering source references, abstention, foreign/missing references, idempotency and read-only observations.
This is a coverage inventory, not an independent security audit, nor new memory behavior or proof of end-to-end privacy. No memory production code changed.

## v6.8: synthetic art resource measurement
The fixed two-color 256x256 fixture is generated in a temporary directory. A warm-up precedes 2–10 timing repetitions and a separate set of traced Python allocation runs. The output records Python, Pillow, OS family, architecture and individual measurements. Tracemalloc is not RSS, and timing is not thermally controlled. No speedup claim is made. No arbitrary workload or agent execution.

## v6.9: validation status
Ten new synthetic test methods cover missing history, escaped HTML, failed observations, invalid input, CLI output, resource report structure and repeatability. These checks do not constitute independent scientific validation. Existing v6.1–v6.5 reference tests remain relevant. Future artistic validation requires human-reviewed examples and explicit limitations.

## v7.0: not yet released
Review stacked PRs and exact dependency chain; verify tests on target environment; review accessibility, test limitations and dependencies. No merge, release, or production service change in this branch.
