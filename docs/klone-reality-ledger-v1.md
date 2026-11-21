# KLONE Reality Ledger v1 – what actually exists in this checkout?

## Purpose

This is a **local, read-only checkout inventory**, not a new authority or a
replacement for KLONE Evidence Forensics. It was added because development
continues simultaneously in main, Council72 intelligence, Limbo Atlas,
Knowledge Atlas and other unmerged feature worktrees.

A source file is not a working service. A test file is not a passed test.
A 200 OK local health response is not an authenticated release. A passing CI
run on another commit is not an Android acceptance test.

The tool deliberately preserves these distinctions.

## Offline quick start in Termux

From the repo/worktree containing this script:

~~~sh
cd ~/klone-next || exit 1
python tools/klone_reality_ledger.py
~~~

This performs no HTTP requests, test execution, database reads, model calls,
deployments or file writes. It prints a JSON inventory to the terminal.

For a readable HTML file, create a **new** file outside the checkout:

~~~sh
cd ~/klone-next || exit 1
python tools/klone_reality_ledger.py \
  --format html \
  --output "$HOME/klone-var/reality-$(date +%Y%m%d-%H%M%S).html"
~~~

To include **three fixed localhost health probes** (optional, explicit):

~~~sh
python tools/klone_reality_ledger.py \
  --probe-local \
  --format html \
  --output "$HOME/klone-var/reality-ports-$(date +%Y%m%d-%H%M%S).html"
~~~

Allowed endpoints only:
- 127.0.0.1:8000/api/health (main)
- 127.0.0.1:8031/api/health (Limbo)
- 127.0.0.1:8041/health (research read-only canary)

Probes make one direct request per endpoint, with a one-second socket timeout,
an 8 KiB response cap, no automatic redirects and no external hostnames. Only
the health state, HTTP status and optional app version enter the report.
Database paths and unrecognized response fields are discarded.

To inspect a **different checkout** without switching its branch:

~~~sh
python tools/klone_reality_ledger.py --root "$HOME/klone-arxiv-e1"
~~~

The script checks 17 capability groups, including Core, Memory, Hypervisor,
Research, Council72, the optional LLM bridge, Limbo, Knowledge Atlas, Noki,
Cognition, Art, Genomics and Evidence. It reads version declarations, looks at
Git HEAD/branch/cleanliness and flags possible tracked runtime artifacts by
filename. It does **not** open the artifacts or inspect their content.

## Interpretation

- source_state=present: all named source paths are ordinary files in this
  checkout. This does not confirm implementation quality, APIs, tests or runtime.
- source_state=partial: some named files exist.
- source_state=not_in_checkout: none of the named files is present here.
  The feature may exist in an unmerged branch, a different layout or another
  repository. The inventory is an intentionally small set of sentinels.
- test_state=files_present: named regression files exist. **No test is run**.
- execution_state=not_executed_by_reality_ledger: remains true in every
  output; importing CI or Android results is a separate, future workflow.
- local_services[].state=not_probed: default, not a failure.
- health_reported_ok: a localhost response reported health OK; not proof of
  identity, database consistency, permissions or deployment readiness.
- working_tree_clean: Git working-tree observation for this checkout only.
- deployment_approved=false: always. This tool never approves deployment.

The flags for version mismatch, blocked Clone Chat egress and potentially
tracked SQLite/log artifacts are **review prompts**, not security findings
based on inspecting confidential content.

## Regression verification

~~~sh
cd ~/klone-next || exit 1
python -m unittest discover -s tests -p test_klone_reality_ledger.py -v
~~~

Focused tests cover no hidden probes, partial/absent/present source mapping,
version mismatch, malformed version declarations, tracked filename warnings,
loopback allowlists, privacy redaction, redirects, HTML injection, immutable
output and symlinked sources.

For wider regression approval, run the repository's own full test matrix on
the **exact same commit**, compare with GitHub CI and run the relevant Termux
smoke tests on the device. None of that is simulated by this utility.

## Next gated integration

1. Attach an immutable, SHA-256-bound source inventory to the existing
   evidence v2 manifest **before** the test run, instead of retrospectively
   claiming test success.
2. Import CI/Android artifacts only through the existing Forensics and
   contract checks; mark missing or mismatched evidence unknown.
3. Link each real capability to a reproducible acceptance test, protected
   API, device/environment and owner-approved release criteria.
4. Add a frontend importer for the **generated local report** after it has
   passed browser and privacy regression tests; do not automatically expose
   a whole-phone inventory from a public endpoint.
5. Review the stacked PR dependency chain and resolve main versus feature
   worktree drift before integrating more network or agent functionality.

No new rights, write API, data sync, online research, model calls or service
restart is granted by this implementation.
