# Hypervisor Runtime Contract

Status: proposed implementation contract
Scope: internal control-plane orchestration only
Write-surface impact: none

## Purpose

KLONE already has room policy, deterministic guards, supervisor metadata, service seams, audit trails, memory provenance, and room-scoped APIs. This contract defines how those pieces are coordinated by one explicit hypervisor runtime without creating a second source of truth.

The hypervisor is a control-plane router and policy coordinator. It is not a domain expert, persistence layer, memory owner, or autonomous source of truth.

## Core invariants

1. **Room first**
   - Every task must resolve an explicit room before room-scoped data is read or written.
   - Cross-room access is never implied by a task or model output.

2. **Policy before delegation**
   - Role access and requested permission are evaluated deterministically before a domain supervisor or worker is invoked.
   - Classification compatibility is checked before governed data crosses a room boundary.

3. **Delegate, do not absorb**
   - The hypervisor routes work to the responsible domain supervisor.
   - Domain logic stays in the domain service/supervisor.
   - The hypervisor does not duplicate MemoryService, BlobService, SimulationService, ArtLabService, DialogueCorpusService, ConstitutionService, or repository behavior.

4. **No hidden write authority**
   - A routing decision does not grant write access.
   - Existing room permissions, approval rules, guards, and service boundaries remain authoritative.
   - Public /v1 capabilities remain read-only until a separately approved write contract exists.

5. **Audit every consequential control-plane decision**
   - Decisions that affect access, routing, approval, execution, or mutation must be attributable.
   - Request/trace/principal/role context must survive delegation.
   - Audit history is append-only and must not become a mutable state store.

6. **Evidence remains source-linked**
   - Memory correction remains status/provenance based.
   - Derived convenience fields such as `corrected` must not become competing persisted truth.
   - Replay must not silently erase correction state, provenance, evidence text, or room identity.

7. **Supervisor boundaries stay explicit**
   - Every room has one declared supervisor.
   - Every declared room supervisor maps to a known agent role.
   - The hypervisor remains visible in every room's allowed-agent set so control-plane routing can be inspected and audited.

8. **Failure is closed, visible, and bounded**
   - Unknown room, incompatible role, incompatible classification, missing permission, or missing supervisor mapping must not silently fall through.
   - A blocked decision should remain inspectable through deterministic guard/audit output.
   - No model is allowed to override a deterministic guard.

## Runtime responsibility split

### Hypervisor

Responsible for:
- resolving the target room;
- carrying request context;
- invoking deterministic policy checks;
- selecting the declared supervisor;
- choosing only explicitly exposed service seams;
- coordinating approval requirements;
- preserving audit and trace context;
- combining bounded domain results;
- surfacing uncertainty and blocked states.

Not responsible for:
- direct repository mutation;
- raw memory correction;
- asset ingestion;
- simulation persistence;
- genomics interpretation;
- art interpretation;
- hidden cross-room joins;
- changing room permissions at runtime.

### Domain supervisors

Responsible for domain-specific orchestration inside the already-approved room and permission envelope.

Current supervisor families include:
- memory supervisor;
- media supervisor;
- genomics supervisor;
- art supervisor;
- simulation supervisor.

### Worker agents

Workers execute bounded tasks delegated by supervisors. Workers never infer broader permissions from the work item they receive.

### Policy and evidence layer

The current control-plane policy/evidence substrate is composed of:
- room registry;
- AccessGuard;
- ClassificationGuard;
- AuditGuard;
- OutputGuard;
- PolicyService;
- AuditService;
- MemoryFacade and source-linked memory detail;
- append-only control-plane audit chain.

## Required routing sequence

A future concrete HypervisorRuntime should follow this order:

1. accept task + request context;
2. resolve explicit room;
3. resolve actor role and requested permission;
4. run AccessGuard;
5. run ClassificationGuard when classified data is involved;
6. stop on blocked decisions;
7. mark approval-required decisions without auto-escalating privileges;
8. resolve the room's declared supervisor;
9. select an explicit service seam;
10. delegate the bounded operation;
11. apply output policy;
12. append audit/trace evidence where the operation contract requires it;
13. return a bounded result with room, supervisor, policy decision, sources, and trace identity visible.

No later step may retroactively weaken an earlier guard decision.

## Phase 2B.3 compatibility

Phase 2B.3 is treated as a completed foundation, not reopened work.

The hypervisor runtime must preserve these established invariants:
- memory corrections remain queryable;
- rejection and supersession remain room-scoped;
- repeated correction calls remain idempotent;
- evidence text and provenance survive correction and replay;
- replay preserves correction state;
- `corrected` stays derived from canonical status rather than becoming an independent persisted flag;
- blocked replay does not create duplicate audit entries.

## Initial automated contract checks

The regression suite should continuously verify:
- exactly one shared hypervisor role exists;
- every room exposes a known supervisor;
- every room allows the hypervisor agent;
- every room keeps the owner role available;
- room permissions reference only known permission levels;
- public /v1 capabilities stay read-only;
- core control-plane seams remain explicit;
- Phase 2B.3 regression tests continue to pass.

## Deliberately out of scope

This contract does not yet add:
- autonomous planning;
- dynamic permission grants;
- cross-room federation;
- background agent swarms;
- write-capable public /v1 routes;
- self-modifying policy;
- supervisor bypass;
- hidden memory mutation;
- model-based policy decisions.

Those require separate, explicit approval and tests.
