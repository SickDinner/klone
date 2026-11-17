# A1.10 verified contract notes and test corrections

Status: **pre-approval review only**. No runtime changes authorized.

## Confirmed source behavior

1. `loadMemorySelection` sets selection, performs parallel detail/provenance/context reads and only updates detail and provenance panels in its error handler. It does **not** reset previously displayed context or answer. This is a confirmed missing-clear path in code; whether it causes an actual unauthorized disclosure depends on browser reproduction and server authorization.
2. `refreshMemoryExplorer` similarly clears only detail and provenance on request failure; old event/episode lists and context may remain.
3. `refreshMemoryAnswer` and `refreshMemoryContextOnly` have independent asynchronous reads and no visible selection generation check. Their failure handlers also do not reset corresponding stored state.
4. `/v1/rooms/{room_id}/changes` returns `change_id`, `object_id`, `change_kind`, `trace_id`, `recorded_at`, `actor`, `summary`. `object_id` is constructed from audit `target_type:target_id`. Only link a selected memory item if its exact object identity is provably the same; otherwise use room-level preview.
5. **Important correction to prior test matrix:** the changes endpoint calls `services.audit.log_control_plane_event` on successful reads (and handles errors with audit logging). Thus it is *read-only for memory/domain objects* but **not zero-write for the audit store**. Tests must allow expected append-only audit events while forbidding domain mutations, unauthorized disclosure and audit-history rewrites. A blanket 'no database writes' assertion is incorrect.

## Reproducible smoke-test procedure (to implement only after approval)

- Fixture A and B in separate rooms, with distinct sentinel strings.
- Select A; then deny/fail B and assert no A sentinel in detail, provenance, context, answer, event list or episode list.
- Delay A responses, select B, resolve B first then A: B remains selected and displayed.
- Change rooms while requests are pending: old-room payloads must not appear.
- Inject escaped markup into source refs and audit summary: no active DOM nodes or script execution.
- Compare audit events before/after an authorized changes read: one expected append-only control-plane event may appear; existing audit rows unchanged.
- For denied changes read, verify no sensitive object IDs in error payload or browser.
- Test exact `object_id` match before any item-specific change link; never infer linkage from timestamp or partial string match.

## Suggested fix order after explicit A1.10 approval

1. Centralized invalidation of all selection-dependent panels and stored data.
2. Monotonic request generation or cancellation guard for list/detail/context/answer.
3. Defensive payload shape checks and consistent URL encoding.
4. Room-scoped changes preview and only contract-supported cross-links.
5. Real browser tests, regression matrix and security review.

Do not merge implementation based solely on static inspection.
