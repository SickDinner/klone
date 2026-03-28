# Current Handoff

Last updated: 2026-03-28

## Current approved phase
Phase G1.2 closeout complete / awaiting next approved phase

## Baseline
- 2B.1 through 2B.5 complete
- memory spine, provenance, replay, correction, contract lock, and stress verification are in place
- read-only query, context, provenance-detail, bounded-answer, and Memory Explorer surfaces exist in repo reality
- A1.1 request context, service seams, and GET /v1/capabilities exist in repo reality
- A1.2 contract shells and append-only control-plane audit chain exist in repo reality
- A1.3 local blob metadata shell exists in repo reality without adding a new /v1 blob route
- A1.4 local object envelope shell exists in repo reality without adding a public /v1 object route
- Phase A1 roadmap bullets are satisfied in current repo reality
- A1.5 public room-scoped object get exists in repo reality
- A1.6 public room-scoped query shell exists in repo reality
- A1.7 public room-scoped blob metadata detail exists in repo reality
- A1.8 public room-scoped audit preview query kind exists in repo reality
- G1.1 read-only ingest preflight manifest exists in repo reality
- G1.2 bounded ingest run manifest history exists in repo reality

## Immediate goal
Phase G1.2 is complete. No further approved G1 substep is enumerated in canonical repo evidence.
Await explicit roadmap extension or approval before widening the ingest spine. Do not reopen completed 2C retrieval, context, provenance, bounded-answer, Memory Explorer, A1.1 seam work, A1.2 audit/contract-shell work, A1.3 blob metadata shell work, A1.4 object envelope shell work, A1.5 public object-get seam work, A1.6 public query seam work, A1.7 public blob metadata detail seam work, A1.8 audit preview query work, G1.1 preflight manifest work, or G1.2 manifest history work.

## Approved scope
- canonical docs closeout after completed Phase G1.2
- verified confirmation that no further post-G1.2 approved substep is currently defined
- duplicate-work prevention
- no unrelated runtime behavior
- no unrelated API widening

## Hard constraints
- do not modify ingest behavior
- do not regress the completed read-only preflight manifest seam at `/api/ingest/preflight`
- do not regress the completed bounded manifest-history seam at `/api/ingest/runs/{run_id}/manifest`
- do not modify evidence_text
- do not add public write endpoints
- do not add semantic search
- do not add embeddings
- do not add fuzzy matching
- do not widen correction behavior
- do not add direct LLM-to-database authority
- preserve room scope and replay determinism
- do not regress the read-only context/answer contract
- do not regress the request-context seam
- do not regress the contract shells or append-only audit-chain linkage on /v1/capabilities
- do not regress the local blob metadata shell or its capability exposure via existing asset routes
- do not regress the local object envelope shell or its capability/readiness visibility through /v1/capabilities
- do not regress the public room-scoped read-only blob-meta seam at `/v1/rooms/{room_id}/blobs/{blob_id}/meta`
- do not regress the public room-scoped read-only object-get seam at `/v1/rooms/{room_id}/objects/get`
- do not regress the public room-scoped read-only query seam at `/v1/rooms/{room_id}/query`
- do not regress the completed `audit_preview` query kind on `/v1/rooms/{room_id}/query`
- do not add async queue workers, resumable jobs, or manifest persistence without a new approved phase
- do not widen manifest history into full file-by-file archival or background processing without a new approved phase
- do not add semantic search, fuzzy matching, embeddings, or query-time synthesis
- do not add /v1/changes, /v1/objects/set, /v1/blobs/upload, or any new blob list/query route beyond the completed A1.7 blob metadata seam
- do not widen supported query kinds beyond `memory_events`, `memory_episodes`, and `audit_preview` without a new approved phase
- do not widen supported object kinds beyond `dataset`, `asset`, `memory_event`, and `memory_episode` without a new approved phase
- do not widen blob semantics beyond deterministic metadata detail over existing asset-backed rows
- do not widen ingest preview into writes, audit side effects, or background workers without a new approved phase

## Required verification
- compile pass
- focused G1.2 tests green
- regression slice for G1.1 green
- full unittest suite green
- local verification if read behavior changes





