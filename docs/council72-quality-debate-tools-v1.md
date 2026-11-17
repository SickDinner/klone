# Council72 Quality, Debate and Public Tools v1

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
