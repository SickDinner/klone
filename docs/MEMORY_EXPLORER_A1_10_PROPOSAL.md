# Memory Explorer A1.10: approval-gated implementation proposal

Status: **proposal only, not approved for implementation**.

## Verified baseline
- README lists A1.9 room-scoped change preview complete.
- Existing read-only routes: `GET /api/memory/events/{event_id}/provenance`, `GET /api/memory/episodes/{episode_id}/provenance`, `GET /api/memory/context/payload`, `GET /v1/rooms/{room_id}/changes`.
- Mission Control already contains Memory Explorer detail, provenance and context panels.
- Governance policy: no implicit expansion of rights; sensitive memory remains room-scoped.

## Proposed A1.10 scope, subject to explicit approval
1. **Provenance UX:** present already-authorized source references and correction state beside event/episode detail. No raw source auto-fetch.
2. **Change-preview linking:** link an already-visible memory item to authorized room-scoped change-preview results, with stable identifiers and explicit empty/denied states. Do not introduce change write APIs.
3. **Context visualization:** show included/excluded counts, query scope, provenance confidence as available; never invent missing fields or cross room boundaries.
4. **Browser smoke tests:** verify healthy/empty/denied responses, escaped untrusted text, navigation, and no network requests outside existing read endpoints.

## Security and release gates
- No new write surface, no live model routing, no new ingestion or background worker.
- Reuse current room and role authorization for every read. No privilege inheritance from UI selection.
- Treat all provenance strings as untrusted and HTML-escape before display.
- Limit preview counts and preserve deterministic ordering; do not leak identifiers on denied requests.
- Unit tests and browser smoke tests on Ubuntu/Windows before merge.
- A1.10 implementation requires separate explicit approval in canonical project docs. This proposal is **not** that approval.

## Other modules: explicitly deferred
- Constitution Layer 2E.1: writes, live routing influence and approval workflows.
- Art Lab V1.2+: comparison UX expansion, batch profiling, OCR, embeddings, drawing clusters.
- Genomics: raw intake, normalization, annotation sandbox, supervisor-gated summaries require separate design and authorization.
- Ingest: OCR, transcription, extraction state machines and advanced dedup require a separately approved ingest phase.

## Suggested acceptance criteria
- Authorized users see only their room's existing provenance and change data.
- Unauthorized requests show a generic denial with no raw record data.
- Browser smoke tests cover escaping and navigation on at least two viewport sizes.
- No database schema changes, migrations, write endpoints or audit history rewrites.
