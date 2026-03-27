# Phase 2B.4 Closeout

## Locked correction contract

Phase 2B.4 does not add new behavior. It locks the Phase 2B.3 correction read contract and records the SQLite bootstrap caveat clearly.

Memory correction state for `memory_events` and `memory_episodes` is:

- `active`
- `rejected`
- `superseded`

Correction metadata is preserved on the row:

- `correction_reason`
- `corrected_at`
- `corrected_by_role`

For superseded events, the system also persists a dedicated room-scoped link table:

- `memory_event_supersessions`

The table stores:

- `id`
- `room_id`
- `old_event_id`
- `new_event_id`
- `reason`
- `created_at`
- `created_by_role`

Rules:

- both events must exist in the same room
- no cross-room supersession links
- no memory-row deletion
- `evidence_text` is never rewritten

## Read contract

Public memory API remains read-only.

Allowed memory routes are:

- `GET /api/memory/events`
- `GET /api/memory/events/{event_id}`
- `GET /api/memory/entities`
- `GET /api/memory/entities/{entity_id}`
- `GET /api/memory/episodes`
- `GET /api/memory/episodes/{episode_id}`
- `GET /api/memory/episodes/{episode_id}/events`

There are no public correction write endpoints.

List route contract remains lean:

- list routes return row records only
- list routes do not expose provenance hydration payloads
- list routes do not expose linked-row hydration payloads

Detail route contract remains additive and stable:

- event detail exposes `status`, `correction_reason`, `corrected_at`, `corrected_by_role`
- episode detail exposes `status`, `correction_reason`, `corrected_at`, `corrected_by_role`
- superseded event detail exposes `superseded_by_id`
- detail routes keep provenance and link hydration

All memory reads remain room-scoped:

- `room_id` is required
- no implicit all-room fallback
- no cross-room leakage

## Replay preservation guarantees

Replay remains deterministic and idempotent.

Replay does not:

- reactivate rejected rows
- undo superseded rows
- change `correction_reason`
- change `corrected_at`
- change `corrected_by_role`
- duplicate `memory_event_supersessions`
- rewrite `evidence_text`

Replay preserves:

- correction state
- normalized provenance
- deterministic episode identity
- room-scoped isolation

## Migration / bootstrap caveat

### Existing SQLite databases

Existing databases require schema bootstrap through the normal app startup path or an explicit `KloneRepository.initialize()` call so that:

- `memory_event_supersessions` is created if missing

This is not a new API migration surface. It is the normal repository bootstrap requirement for an already-initialized local SQLite file.

### Fresh vs existing status constraints

Fresh databases created after Phase 2B.4 get the tighter `CHECK(status IN ('active','rejected','superseded'))` definition on new `memory_events` and `memory_episodes` tables.

Existing SQLite databases are not table-rebuilt automatically just to add the new `CHECK` constraint. For already-existing tables:

- allowed statuses are still enforced by repository/service validation
- correction behavior remains deterministic
- the database-level `CHECK` is only guaranteed on freshly created tables unless a future explicit migration rebuild is introduced

## Verification lock

Phase 2B.4 verification should continue to prove:

- list routes remain lean
- detail routes expose correction fields
- no cross-room leakage
- supersession visibility is stable
- correction fields survive replay
- memory API write surface did not expand
