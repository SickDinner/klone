# KLONE CI + Android evidence contract

This workflow records **two independent observations**, never one inferred pass.

## GitHub CI (automated)

The `KLONE regression guard` workflow runs on pull requests and main.
Each OS/Python matrix job uploads a `klone-ci-evidence-*` JSON artifact,
with source, commit, ref, run ID, attempt, platform and job status.
Artifacts are retained for 30 days. The manifest is evidence about the
CI job, **not** proof that Android passed.

## Android / Termux (device-originated)

A separately authenticated Termux bridge polls issues labeled
`klone-termux-task`, accepts only trusted authors and the fixed
`status`, `git_status`, `health`, `tests` actions, and posts
its observed results back to the issue. This is independent of GitHub CI.

To run the device acceptance checks, create three separate issues with
the label and the exact JSON body:

- `{"action":"status"}`: record the device commit
- `{"action":"health"}`: record the local server health
- `{"action":"tests"}`: record the device test suite

The device must be running `tools/termux_bridge.py watch`, or
`once` must be invoked manually.

## Acceptance gate (human-reviewed)

Treat a commit as accepted for Android only if:

1. GitHub CI for the **same commit** passed on its configured matrix.
2. The device's `status` response reports that commit (short SHA is
   sufficient only when it resolves unambiguously).
3. The device's `health` and `tests` issue comments have exit code 0,
   are fresh for the intended validation window, and are linked in the review.
4. An operator reviews both evidence sources. No automatic merge,
   deployment or permission elevation follows from these reports.

If the device is on an older commit, classify the outcome as
`pending_android_validation`, not as passed or failed.

## Security and provenance limitations

Issue comments are operational logs, not a tamper-proof audit ledger.
They can contain sensitive local paths or test data: prefer private
repositories, redact secrets, and never post private memory payloads.
GitHub artifacts expire. Durable, cryptographically verifiable ingestion
into KLONE's own audit database is **not implemented** by this change.
That requires a separately reviewed importer with strict validation,
identity binding, deduplication and fail-closed persistence.
