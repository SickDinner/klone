# Council72 Quality, Debate and Public Tools v1

## Android real-data outcome and v1.1 size fix (17 Nov 2026)

Verified on the user's OnePlus Android / Termux (commit 83bd136):
- Offline quality audit: 12/12 new unit tests, all 72 roles accounted
  for, 10/10 public citation card IDs used at least once, 0 Memory writes.
- Debate preview and public local tools: passed, 0 API requests.
- The FIRST separately approved debate-live attempt stopped at the
  FIRST cross-examination stage with the error:
  model request exceeds its public-data budget.
  The old 48,000-byte request limit rejected the constructed JSON body
  BEFORE HTTP, so that failed attempt did not produce a paid model call.
- Previous output had "0 high lexical-overlap pairs"; this is NOT
  evidence of semantic specialization or low repetition. The eight
  rings' actual findings showed considerable semantic repetition.

### Fixed in subsequent v1.1 commits

- The debate stage now samples bounded but REAL statements from all
  64 specialist roles and findings from all eight rings.
- Choose the largest of five deterministic compression profiles that
  fits the ACTUAL UTF-8 serialized OpenAI Responses body, including
  the full strict JSON schema and instructions, under 48 kB.
- Include source snippets from both arXiv versions where possible,
  a public-only discrepancy summary, founder disagreement and
  abbreviated founder synthesis. This is a lossy sample:
  full original ring data remains in the immutable local JSON file.
- Before EACH paid call, re-check body size after prior model turns
  have been safely compacted. No silent request-body overflow.
- The zero-cost debate-preview now includes the FIRST real request's
  byte count, selected compression profile and all 64 retained role
  IDs. Subsequent turns require their actual previous outputs and
  are checked just before sending.
- Store prompt_compaction_version=2 in the checkpoint context and
  write to debate-v2-* session folders; old v1 answered checkpoint
  files block new paid calls rather than being repurchased silently.
  The user's initial v1 run failed before HTTP, so it has no paid
  response to migrate.

These changes are tested with large, multi-byte Finnish text and
long prior model arguments. A passing mock test is NOT a claim that
the user's first real debate-live v1.1 has already succeeded.

### Termux sequence after pulling the fixed commit

    cd ~/klone-arxiv-e1 || exit 1
    git fetch origin feat/council72-quality-debate-tools-20261117 || exit 1
    git switch --detach FETCH_HEAD || exit 1
    bash scripts/klone-council72-quality-phone.sh debate-preview

This preview is free and should show something like:
Mallisyötteen preflight: X / 48000 tavua
Mukana asiantuntijarooleja: 64

The later debate-live remains an OPTIONAL, separately approved,
up-to-three-call billable action. Do not restart any debate-live
in parallel with an already running session.

## Scope and factual boundary

This component builds on Council72 Intelligence Bridge PR #181.
The user's Android 17 Nov 2026 trial confirmed 9 model analyses: 8 new
API calls plus 1 reused ring-1 probe, and no Memory Core writes.

This extension is OFFLINE by default. Its analyses and scores are
heuristic: they do not authenticate original scientific sources or
establish that the 72 role profiles are independent intelligences.

## A — Read all 72 outputs, offline

Quality Lab verifies the complete Council72 resume report and original
E11.11 source report, including report SHA256, per-ring request and
response hashes, exact canonical member IDs, approved citation IDs,
founder synthesis request and owner-review-only status.

It produces:
- all 64 specialist member observations and challenges, grouped by ring;
- all 8 founder positions and explicit stated disagreements;
- a task description for each role;
- ring-level source-card coverage and missing source cards;
- within-ring lexical Jaccard overlap candidates;
- numeric claims needing direct source checks;
- explicit heuristic limitations, not a "truth score".

The original research claims cannot be evaluated from only the CLI
success log. The full local report is needed for factual interpretation.

## B — Actual three-turn model debate (opt-in)

Round 1: cross-examiner challenges concrete source-grounded assertions.
Round 2: defender offers its strongest warranted replies.
Round 3: neutral arbiter records unresolved disputes, caveats and
falsifiable experiments, always requiring owner review.

The same GPT model can perform all three turns; there is no claim of
three independent model agents. The model receives bounded extracts
from all 64 specialist roles, ring findings/counterarguments and
founders' synthesis. Inputs are untrusted data, never executable orders.

The default is a debate preview with ZERO network/API calls. Real
debate-live requires fresh explicit public-data confirmation, an
API key, and the approval token HYVAKSY_3_GPT_KUTSUA.
The paid run has at most three OpenAI Responses calls, no tool
calls issued by the model, store=false, and no automatic retries.
Every received response is checkpointed before local validation;
a rejected reply is not silently purchased again.

## C — Public, read-only research tools

The local dispatcher has only three allowlisted functions:
- card_lookup: retrieve one local public E11.11 card by verified ID
- discrepancy_counts: summarize source card discrepancy classes
- member_profile: retrieve a canonical Council72 role profile

No arbitrary URL, shell, SQL, file paths or Memory Core access.
The debate orchestrator uses bounded local card lookups and discrepancy
summary before its model input; these tools cannot be invoked
autonomously by the model. External research browsing is NOT yet
implemented and requires a separate hypervisor authorization review.

## Android Termux — ZERO COST FIRST

    cd ~/klone-arxiv-e1 || exit 1
    git fetch origin feat/council72-quality-debate-tools-20261117 || exit 1
    git switch --detach FETCH_HEAD || exit 1

    bash scripts/klone-council72-quality-phone.sh audit
    bash scripts/klone-council72-quality-phone.sh debate-preview
    bash scripts/klone-council72-quality-phone.sh tools

The script detects the most recent existing Council72 resume JSON and
E11.11 evidence JSON in ~/klone-var/e11, runs mock-network tests, and
creates new JSON reports without modifying earlier files.

## Optional, ONLY AFTER A NEW BILLABLE-CALL APPROVAL

Before this step, personally approve transmitting the selected public
research excerpts and council commentary to the OpenAI API. Up to
three new billable API calls may occur; prior approvals DO NOT apply.

    cd ~/klone-arxiv-e1 || exit 1
    read -r -s -p 'OpenAI API key: ' OPENAI_API_KEY
    printf '\n'
    export OPENAI_API_KEY
    export KLONE_COUNCIL72_CONFIRM_PUBLIC=VAHVISTAN_JULKISUUDEN
    export KLONE_COUNCIL72_DEBATE_APPROVAL=HYVAKSY_3_GPT_KUTSUA

    bash scripts/klone-council72-quality-phone.sh debate-live
    RESULT=$?

    unset OPENAI_API_KEY
    unset KLONE_COUNCIL72_CONFIRM_PUBLIC
    unset KLONE_COUNCIL72_DEBATE_APPROVAL
    echo "Lopetuskoodi: $RESULT"

An incomplete or invalid reply stops the debate. Do not remove the
checkpoint files to hide a failed billable response.

## Definition of done

- Complete authenticated-to-local-input 72-role audit on Android,
- Offline generated adversarial prompt pack and public tool receipts,
- separately approved three-turn real debate or an offline-only demo,
- all unit and GitHub CI regression tests green,
- no autonomous action, model-authorized voting, or memory write.

Next step is controlled qualitative comparison against a single GPT
analysis, not automatic growth into 72 costly model instances.
