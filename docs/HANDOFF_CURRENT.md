# Current Handoff

Last updated: 2026-04-01

## Current approved phase
Phase 2B.6 dialogue corpus shell complete

## Baseline
- 2B.1 through 2B.5 complete
- 2B.6 read-only dialogue corpus shell exists in repo reality
- memory spine, provenance, replay, correction, contract lock, and stress verification are in place
- read-only query, context, provenance-detail, bounded-answer, and Memory Explorer surfaces exist in repo reality
- A1.1 request context, service seams, and GET /v1/capabilities exist in repo reality
- A1.2 contract shells and append-only control-plane audit chain exist in repo reality
- A1.3 local blob metadata shell exists in repo reality without adding a new /v1 blob route
- A1.4 local object envelope shell exists in repo reality without adding a public /v1 object route
- A1.5 public room-scoped object get exists in repo reality
- A1.6 public room-scoped query shell exists in repo reality
- A1.7 public room-scoped blob metadata detail exists in repo reality
- A1.8 public room-scoped audit preview query kind exists in repo reality
- A1.9 public room-scoped change preview seam exists in repo reality
- G1.1 read-only ingest preflight manifest exists in repo reality
- G1.2 bounded ingest run manifest history exists in repo reality
- G1.3 local ingest queue shell exists in repo reality
- G1.4 local resumable ingest queue exists in repo reality
- G1.5 bounded ingest queue history/detail seam exists in repo reality
- V1.1 read-only asset formal metrics exists in repo reality
- V1.2 bounded room-scoped art comparison seam exists in repo reality
- 2E.1 read-only constitution shell exists in repo reality

## Immediate goal
Phase 2B.6 is complete. No further approved 2B.6, 2E, A1, G1, or V1 substep is enumerated in canonical repo evidence.
Await explicit roadmap extension or approval before widening the dialogue-corpus shell, the constitution layer, the public control-plane seam, the ingest spine, or the art-lab. Do not reopen completed 2C retrieval, context, provenance, bounded-answer, Memory Explorer, 2B.6 dialogue-corpus work, A1.1 seam work, A1.2 audit/contract-shell work, A1.3 blob metadata shell work, A1.4 object envelope shell work, A1.5 public object-get seam work, A1.6 public query seam work, A1.7 public blob metadata detail seam work, A1.8 audit preview query work, A1.9 change preview seam work, G1.1 preflight manifest work, G1.2 manifest history work, G1.3 local queue shell work, G1.4 local resumable queue work, G1.5 queue history work, V1.1 asset formal metrics work, V1.2 bounded comparison work, or 2E.1 constitution shell work.

## Approved scope
- read-only dialogue corpus analysis over extracted local Messenger exports and ChatGPT export JSON files
- root-folder discovery that selects the richest Messenger export candidate without merging partial exports
- Mission Control visibility for the dialogue corpus shell
- service seam and capability visibility through `/v1/capabilities`
- no unrelated runtime behavior beyond the completed 2B.6 shell

## Hard constraints
- do not modify ingest behavior
- do not regress the completed read-only dialogue corpus seam at `/api/dialogue-corpus/analyze`
- do not widen dialogue corpus analysis into memory writes, durable relationship labels, OCR/transcription, embeddings, sentiment scoring, or psychological inference without a new approved phase
- do not regress the completed read-only preflight manifest seam at `/api/ingest/preflight`
- do not regress the completed bounded manifest-history seam at `/api/ingest/runs/{run_id}/manifest`
- do not regress the completed local ingest queue shell at `/api/ingest/queue`
- do not regress the completed explicit queue execution shell at `/api/ingest/queue/{job_id}/execute`
- do not regress the completed explicit queue cancellation shell at `/api/ingest/queue/{job_id}/cancel`
- do not regress the completed bounded queue history seam at `/api/ingest/queue/{job_id}/history`
- do not regress the completed room-scoped change preview seam at `/v1/rooms/{room_id}/changes`
- do not regress startup recovery that marks orphaned queue jobs as `interrupted`
- do not regress interrupted job reuse on POST `/api/ingest/queue` for the same room/root path
- do not regress manual resume behavior for `interrupted` queue jobs through the existing execute route
- do not regress the completed read-only art metrics seam at `/api/art/assets/{asset_id}/metrics`
- do not regress explicit non-image rejection for art metrics
- do not regress the completed bounded art comparison seam at `/api/art/assets/compare`
- do not regress the completed read-only constitution shell at `/api/constitution`
- do not widen art metrics into personality inference, clinical interpretation, OCR, embeddings, or batch profiling without a new approved phase
- do not widen art comparison into embeddings, semantic similarity, clustering, batch writeback, or `/v1` expansion without a new approved phase
- do not widen constitution into write routes, live routing influence, self-modification, or agentic self-editing without a new approved phase
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
- do not regress the public room-scoped read-only change preview seam at `/v1/rooms/{room_id}/changes`
- do not widen queue history into full file-by-file archival or background processing without a new approved phase
- do not add `/v1/changes/{change_id}`, `/v1/objects/set`, `/v1/blobs/upload`, or any new blob list/query route beyond the completed A1.7 blob metadata seam
- do not widen supported query kinds beyond `memory_events`, `memory_episodes`, and `audit_preview` without a new approved phase
- do not widen supported object kinds beyond `dataset`, `asset`, `memory_event`, and `memory_episode` without a new approved phase

## Required verification
- focused 2B.6 tests green
- focused 2E.1 tests green
- compile pass
- focused A1.9 tests green
- regression slice for A1.2, A1.6, and A1.8 green
- focused G1.3 and G1.4 tests green
- focused G1.5 tests green
- focused V1.1 tests green
- focused V1.2 tests green
- regression slice for G1.1 green
- full unittest suite green
- local verification if read behavior changes
