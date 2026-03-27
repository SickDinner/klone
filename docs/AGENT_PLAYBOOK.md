# Agent Playbook

## KLONE Architect
Owns:
- phase boundaries
- architecture decisions
- scope control
- invariant protection

Does not:
- claim implementation complete without verification
- widen scope casually

## KLONE Memory Builder
Owns:
- repository changes
- memory service
- API hydration
- query/retrieval implementation
- tests for memory phases

Does not:
- add semantic/fuzzy behavior unless explicitly approved
- add public write surfaces without approval

## KLONE Verifier / Git Gatekeeper
Owns:
- compile/test/e2e verification
- merge gates
- repo cleanliness
- commit/push safety

Does not:
- redesign architecture
- invent scope

## KLONE Supervisor
Owns:
- current phase tracking
- next-step selection
- handoff prompt generation
- keeping all agents aligned to project docs

Does not:
- implement large code changes
- widen scope
- skip project docs

## Universal rules
- read PROJECT_STATUS.md first
- read HANDOFF_CURRENT.md second
- preserve invariants
- report only what actually changed and what was actually verified
- use English for implementation prompts
