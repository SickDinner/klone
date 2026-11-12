# CI verification gate

The offline verifier `klone.ci_run_gate.verify_ci_run` rejects mismatched
repository, SHA, run identity, incomplete workflow, missing required jobs,
duplicate jobs, or any non-successful job.

The **caller must retrieve run and job JSON through an authenticated GitHub
API connection** and pin the expected repository, SHA and required job names
from trusted configuration. Untrusted issue comments and manually authored
JSON are not evidence of authenticated GitHub API provenance.

This gate is an intermediate primitive, not an automatic deployment approval.
The returned `verified_success` means the supplied payload passed local
consistency checks, conditional on caller authentication. It does not attest
Android device identity, Termux execution or artifact contents.

Next: authenticated API fetcher with retry bounds and independent expected
SHA; durable report generation and human review before deployment.
