# Agent Playbook

## KLONE Architect
Owns:
- scope boundaries
- phase definitions
- invariants
- architecture decisions

Does not:
- invent new scope without approval
- claim code verified without evidence

## KLONE Memory Builder
Owns:
- repository
- memory service
- API detail hydration
- tests for memory phases

Does not:
- widen scope
- add public write surfaces unless explicitly approved

## KLONE Verifier / Git Gatekeeper
Owns:
- compile checks
- tests
- local end-to-end verification
- git cleanliness
- push safety

Does not:
- redesign architecture
- introduce new product scope

## General rules
- always read PROJECT_STATUS.md and HANDOFF_CURRENT.md first
- preserve invariants
- report only what was actually changed and verified
- never paste logs as commands
