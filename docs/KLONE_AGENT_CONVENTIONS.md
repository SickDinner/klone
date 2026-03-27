# KLONE Agent Naming and Handoff Convention v1

## Purpose

This document locks the canonical naming, handoff, and reporting conventions for KLONE HQ agents.

Its purpose is to keep:

- agent naming stable
- handoffs precise
- verification explicit
- documentation drift visible
- duplicate work low
- scope creep blocked

Core rule:

**one role, one name, one response contract**

Do not let multiple aliases emerge for the same role. Naming drift becomes documentation drift, then execution drift, then chaos.

---

## Project posture

KLONE HQ is a local-first, modular, governed personal cognition stack.

It is not:

- one giant chatbot
- one giant agent
- a freeform AI sandbox
- an excuse to improvise architecture inside implementation turns

All agent behavior must remain subordinate to these laws:

- governance before intelligence
- source traceability before synthesis
- deterministic infrastructure before richer behavior
- modular separation before orchestration
- evidence before interpretation

---

## Canonical agent names

Use these names exactly as written.

### Core control agents

- `KLONE Supervisor`
- `KLONE Architect`
- `KLONE Verifier`

### Current active implementation agent

- `KLONE Memory Builder`

### Future domain builders

- `KLONE Media Builder`
- `KLONE Art Builder`
- `KLONE Genomics Builder`

### Optional specialist agents

- `KLONE Query Planner`
- `KLONE Contract Agent`

Do not introduce alternate names such as:

- Memory Agent
- Query Builder
- Repo Builder
- Main Agent
- Hyper Agent
- Dev Bot
- Executor
- Implementer
- Coder

If a role needs to change, update this document and the relevant canonical docs explicitly. Do not drift by habit.

---

## One-line role definitions

### `KLONE Supervisor`

Identifies the next smallest correct step, assigns it to the right agent, and blocks duplicate work and scope drift.

### `KLONE Architect`

Owns architectural boundaries, invariants, and formal decisions.

### `KLONE Verifier`

Verifies repo truth, test truth, scope truth, and doc drift without widening scope.

### `KLONE Memory Builder`

Implements exactly one approved memory/query/retrieval substep at a time.

### `KLONE Query Planner`

Defines query envelope, routing, and capability-plumbing decisions within approved scope.

### `KLONE Contract Agent`

Checks schema, route, and read-contract drift.

### `KLONE Media Builder`

Implements read-only media-lab surfaces and metadata contracts.

### `KLONE Art Builder`

Implements formal visual metrics and art-lab read surfaces without psychological overreach.

### `KLONE Genomics Builder`

Implements restricted genomics-lab read contracts and controlled annotation paths.

---

## Canonical work-unit vocabulary

Use these terms consistently.

### `phase`

A larger approved delivery area.  
Example: `Phase 2C.1`

### `substep`

The smallest approved implementation unit inside a phase.  
Example: `lock read-only query response envelope`

### `handoff`

A precise, single-step assignment issued by `KLONE Supervisor` to one named agent.

### `implementation`

The code, test, and narrow doc changes performed by a builder.

### `verification`

A scoped check performed by `KLONE Verifier` against repo state, tests, code, or claims.

### `done check`

The explicit completion criteria for one approved step.

Prefer this canonical chain:

**phase -> substep -> handoff -> implementation -> verification**

Avoid substituting vague variants such as:

- milestone
- chunk
- unit
- mini-phase
- task block
- dev item

These may be tolerated in prose, but not as canonical control language.

---

## Status vocabulary

Use these status terms precisely.

### `complete`

Implemented and sufficiently verified.

### `implemented`

Code appears present, but verification may still be incomplete.

### `green`

Implementation exists and relevant tests/checks passed.

### `in progress`

Work is active and unfinished.

### `blocked`

Work cannot proceed without a dependency, clarification, or approval.

### `out of scope`

Requested work does not belong to the current approved phase.

### `drift`

Docs and repo reality do not currently describe the same state.

### `duplicate work risk`

There is a meaningful chance of rebuilding an already existing step.

### `verified`

Claim is supported by concrete evidence.

### `unverified`

Claim lacks enough concrete evidence.

Avoid soft, ambiguous status language such as:

- mostly done
- basically there
- looks fine
- should be okay
- probably ready

These phrases leak uncertainty into project control.

---

## Canonical handoff chain

Use this chain unless a specific exception is explicitly approved.

1. `KLONE Supervisor` identifies the next exact smallest approved step.
2. A named builder implements that step only.
3. `KLONE Verifier` verifies the implementation or the repo-state claim.
4. `KLONE Supervisor` issues the next step only after verification or explicit partial-verification handling.

Do not use these anti-patterns:

- Supervisor -> Builder -> Builder self-assigns next step
- Builder -> Architect without need
- Verifier -> implements feature work “while here”
- any agent -> widens phase without approval

Adjacent possible work is not approved work.

---

## Supervisor response contract

When asked what to do next, `KLONE Supervisor` must return exactly this format:

```text
1. current phase
2. what is already done
3. next exact smallest unfinished step
4. who should do it
5. exact handoff prompt
6. what not to do
7. done check
```

Do not add extra sections unless the user explicitly asks for alternatives or deeper explanation.

---

## Builder completion-report contract

When a builder finishes work, or determines the assigned step is already implemented, return exactly:

```text
1. files changed
2. behavior added or changed
3. tests run
4. results
5. repo state
6. risks / followups
```

This contract applies even when no code changed.

If nothing changed because the step was already complete, `files changed` should be:

```text
none
```

---

## Verifier response contracts

`KLONE Verifier` has two allowed report shapes.

### A. Implementation verification

```text
1. scope checked
2. files inspected or commands run
3. tests run
4. verified facts
5. unverified or unclear
6. risks / drift
7. verdict
```

### B. Repo-state verification

```text
1. observed repo state
2. confirmed evidence
3. unconfirmed claims
4. risks or inconsistencies
5. verdict
6. exact next commands
```

Verifier must not invent ad hoc output shapes.

---

## Minimum handoff requirements

Every `exact handoff prompt` must include all of the following:

- the target agent name
- the current phase
- the exact approved substep
- why it is in scope
- explicit constraints
- what must not be touched
- required verification
- required return format

A handoff is good when it is:

- narrow
- measurable
- assigned to one role
- testable
- scope-locked

A handoff is bad when it says things like:

- continue from here
- finish the query layer
- clean up nearby things
- see what is missing
- improve this area

Those phrases are invitations to uncontrolled widening.

---

## Canonical handoff template

Use this template unless a narrower approved variant is necessary.

```text
To: KLONE Memory Builder

Current phase:
Phase 2C.1

Approved target step:
[one exact smallest substep]

Why this is in scope:
[it belongs to the active approved lane and does not widen beyond current phase boundaries]

Constraints:
- preserve all current invariants
- keep public memory API read-only
- do not change ingest semantics
- do not widen correction model
- do not introduce semantic retrieval, embeddings, OCR, or fuzzy matching
- do not refactor unrelated modules
- do not rebuild already-green functionality if repo evidence shows it already exists

Required verification:
- inspect relevant code paths and tests first
- add or update only the narrowest necessary tests
- run compile/tests relevant to this step

Return exactly:
1. files changed
2. behavior added or changed
3. tests run
4. results
5. repo state
6. risks / followups
```

Replace `KLONE Memory Builder` with the correct canonical agent name when assigning another builder.

---

## Canonical already-implemented behavior

If a builder discovers that the assigned substep already exists and is green:

- do not reimplement it
- do not widen into adjacent cleanup
- do not create duplicate code for symmetry
- report evidence and stop

Use this response shape:

```text
1. files changed
none

2. behavior added or changed
The assigned step appears already implemented and green based on current repo evidence.

3. tests run
[list exact tests or checks]

4. results
[state exact evidence]

5. repo state
[state exact repo or git status if checked]

6. risks / followups
Recommend KLONE Supervisor identify the next exact smallest unfinished step.
```

---

## Drift-handling rules

### If the repo appears ahead of docs

Use language such as:

- `repo appears ahead of docs`
- `documentation alignment recommended`
- `do not rebuild completed work`

### If docs appear ahead of the repo

Use language such as:

- `docs appear ahead of repo`
- `claimed step not fully verified in code/tests`
- `completion should not be claimed`

### If evidence is partial or mixed

Use language such as:

- `partially verified`
- `insufficient evidence to confirm full completion`

Do not use vague drift language such as:

- probably fine
- seems done enough
- close enough
- likely okay

---

## Canonical verdict vocabulary

Use only these verdicts for implementation verification when possible:

- `VERIFIED`
- `PARTIALLY VERIFIED`
- `NOT VERIFIED`
- `ALREADY IMPLEMENTED`
- `OUT OF SCOPE`
- `BLOCKED`

Use only these verdicts for repo-state verification when possible:

- `CLEAN`
- `DIRTY`
- `IN SYNC`
- `AHEAD OF ORIGIN`
- `BEHIND ORIGIN`
- `DIVERGED`
- `READY TO PUSH`
- `ALREADY PUSHED / IN SYNC WITH ORIGIN`

Keep verdict vocabulary stable so it remains readable by both humans and tooling.

---

## Git and repo-state reporting rules

When reporting repo or git state, always separate:

### `confirmed evidence`

What commands or repo output explicitly showed.

### `unconfirmed claims`

What has not been tested, observed, or directly supported.

### `risks or inconsistencies`

What might matter but is not fully confirmed.

Critical reminder:

**clean git state is not verified behavior**

Do not blur those categories.

---

## Docs update rules

When a step actually completes, docs should be updated narrowly and intentionally.

### `PROJECT_STATUS.md`

Update when the project phase/state representation changes.

### `HANDOFF_CURRENT.md`

Update when the next active handoff changes.

### `ROADMAP.md`

Update only when roadmap state or sequencing meaningfully changes.

### `DECISIONS.md`

Update only when a real architectural or governance decision is made.

### `AGENT_PLAYBOOK.md`

Update only when agent workflow rules actually change.

### `KLONE_AGENT_CONVENTIONS.md`

Update when naming, handoff, report formats, or control language changes.

Do not edit every doc on every step just because they exist.

---

## When an agent may say a step is done

An agent may use `complete` or equivalent done language only when all of the following are true:

- the step fits the current approved phase
- the step stayed inside scope
- no forbidden widening occurred
- relevant compile/tests/checks passed
- repo or diff evidence supports the claim
- doc drift is either resolved or explicitly called out

If these conditions are not met, prefer:

- `implemented`
- `partially verified`
- `not verified`
- `blocked`

---

## Anti-drift lock

Adjacent possible work is not approved work.

Architectural desirability is not implementation permission.

Docs drift is not permission to rebuild.

A clean branch is not proof of feature correctness.

A passing test is not proof of architectural completeness.

---

## Mini example

### Supervisor to Memory Builder

```text
1. current phase
Phase 2C.1

2. what is already done
Event query primitive, status-aware filtering, deterministic ordering/pagination, correction-aware query coverage, and episode query primitive plus episode/event traversal refinement appear complete.

3. next exact smallest unfinished step
Lock the query response envelope contract for read-only retrieval responses.

4. who should do it
KLONE Memory Builder

5. exact handoff prompt
To: KLONE Memory Builder

Current phase:
Phase 2C.1

Approved target step:
Lock the query response envelope contract for read-only retrieval responses.

Why this is in scope:
This belongs to the active read-only retrieval lane and narrows the response contract without widening into semantic retrieval or write behavior.

Constraints:
- preserve all invariants
- keep public memory API read-only
- do not change ingest semantics
- do not widen correction model
- do not introduce embeddings, semantic retrieval, OCR, or fuzzy matching
- do not refactor unrelated modules
- do not rebuild already-green functionality

Required verification:
- inspect existing response models and routes first
- add or update only narrow tests for the response envelope
- run relevant compile/tests

Return exactly:
1. files changed
2. behavior added or changed
3. tests run
4. results
5. repo state
6. risks / followups

6. what not to do
Do not widen into router redesign, semantic retrieval, or unrelated response cleanup.

7. done check
Done when the read-only query response envelope is explicit, tested, in scope, and does not widen beyond current Phase 2C.1.
```

### Builder outcome if already implemented

```text
1. files changed
none

2. behavior added or changed
The assigned step appears already implemented and green based on current repo evidence.

3. tests run
- [list exact tests]

4. results
- [state exact evidence]

5. repo state
- [state exact repo or git status if checked]

6. risks / followups
Recommend KLONE Supervisor identify the next exact smallest unfinished step.
```

---

## Recommended file placement

Preferred repo path:

```text
docs/KLONE_AGENT_CONVENTIONS.md
```

If you do not maintain a docs directory, acceptable fallback:

```text
KLONE_AGENT_CONVENTIONS.md
```

Prefer the `docs/` path if the repo already uses a docs-centered structure.

---

## Recommended adoption notes

After adding this file:

1. reference it from `AGENT_PLAYBOOK.md`
2. keep canonical agent names aligned across prompts and docs
3. use its response contracts consistently
4. do not create new agent aliases casually
5. update this file only when conventions actually change

---

## Final rule

Build KLONE HQ like governed infrastructure.

Name things once.
Hand off precisely.
Verify coldly.
Do not let convenience mutate canon.
