# A1.10 browser implementation handoff: source-verified findings

Status: **review notes only; implementation requires separate canonical approval**.

Inspected `src/klone/static/app.js` on `main` after the research-health merge.

## Existing UI wiring
- `renderMemoryProvenance(kind, provenanceDetail)` already renders lineage, seed basis, membership/full provenance, source references, correction reason.
- `renderMemoryContext(contextPayload)` already renders included/excluded context, warnings and source references.
- `loadMemorySelection(kind,id)` fetches detail, provenance and context in parallel and renders all three.
- `escapeHtml` and `chips` escape many dynamic strings.
- `GET /v1/rooms/{room_id}/changes` is documented in README but not yet visibly linked from the Memory Explorer selection flow.

## Concrete review findings and proposed tests

### F1: stale context after failed detail/provenance fetch
In `loadMemorySelection` the catch handler clears the detail and provenance UI, but does not call `renderMemoryContext(null)` or reset `state.memory.contextPayload` / `state.memory.detail`. A previously selected record's context may remain visible after a denied/failed selection. **Treat as potential confidentiality/UI integrity defect** until reproduced. Test: load authorized A, switch to denied B, assert no A detail/provenance/context remains. Also check `state.memory.answer` and its displayed panel.

### F2: race between rapid selections
Parallel fetches have no visible request-token guard in `loadMemorySelection`. If A resolves after B, A can overwrite B's panels. Test with delayed responses, switch A -> B, assert only B is rendered. On room switch, invalidate all pending requests.

### F3: event URL encoding
Event detail/provenance URL interpolates `id` without `encodeURIComponent`, unlike episode paths. If IDs are numeric only, exposure is limited, but test adversarial IDs and normalize both paths.

### F4: context payload shape
`renderMemoryContext` directly accesses `included_context.length`, `excluded_context.length`, `warnings.length`, `context_package.provenance_summary.source_refs`. Validate the API contract and show a controlled error for partial/invalid payloads rather than throwing and retaining stale content.

### F5: change-preview authorization
Do not link by guessed IDs or global audit records. Query only the existing room-scoped `/v1/rooms/{room_id}/changes` endpoint and cross-link records only if the response itself contains a supported exact identifier. If no deterministic join key exists, display a room-level preview without implying item linkage.

## Proposed safe patch sequence after approval
1. First isolate selection lifecycle with monotonic request generation and explicit panel resets on selection/room change.
2. Add error/denied/empty UI states without exposing server exception bodies or old records.
3. Add change-preview read-only panel only after verifying actual response schema and access behavior.
4. Add browser smoke tests covering F1–F5, HTML escaping, 360px/1280px layouts and network method assertions.
5. Verify all existing tests and supported CI matrices, then request review before merge.

No changes to runtime code or privileges are made by this document.
