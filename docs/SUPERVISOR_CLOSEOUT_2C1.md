1. current phase
Phase 2C.1: Query / Retrieval Primitives, at closeout threshold.

2. what is already done
Phase 2B.1 through 2B.5 are complete.
Phase 2C.1 repo-backed complete work includes:
- room-scoped memory event query primitive
- status-aware filtering for memory events
- deterministic ordering and pagination
- correction-aware query coverage
- episode query primitive
- episode-side deterministic filtering
- episode/event traversal refinement
- detail-level provenance exposure
- query/list provenance summary exposure

Focused verification passed in tests.test_memory_phase_2c1 with 6/6 tests green.
Code commit: 8839716
Docs alignment commit: 1664e24

3. next exact smallest unfinished step
Perform a narrow 2C.1 closeout audit and determine whether any exact repo-backed 2C.1 gap still exists. If none exists, mark 2C.1 complete in canonical docs and identify the next approved phase/substep from repo evidence only.

4. who should do it
KLONE Supervisor

5. exact handoff prompt
KLONE Supervisor: perform one narrow closeout step only. Read docs/PROJECT_STATUS.md first, docs/HANDOFF_CURRENT.md second, then docs/ROADMAP.md, docs/DECISIONS.md, docs/AGENT_PLAYBOOK.md, and docs/KLONE_AGENT_CONVENTIONS.md. Use current repo reality only. Treat these facts as already verified unless repo evidence contradicts them: Phase 2B.1 through 2B.5 complete; Phase 2C.1 event query/filtering/ordering/correction-aware coverage complete; episode query plus episode/event traversal complete; detail-level provenance already exists; query/list provenance summary exposure implemented and tested green in tests.test_memory_phase_2c1; related commits include 8839716 for code and 1664e24 for docs alignment. Task: determine whether any exact unfinished 2C.1 read-only retrieval substep still remains. If none remains, update only the canonical docs needed to mark 2C.1 complete and name the next approved phase/substep from repo evidence only. If a gap does remain, name exactly one smallest unfinished 2C.1 substep and do not widen beyond it. Preserve all invariants: immutable evidence_text, room-scoped reads only, no cross-room leakage, deterministic replay, correction by status/supersession, provenance-first, and read-only public memory API. Return exactly: 1. current phase 2. what is already done 3. next exact smallest unfinished step 4. who should do it 5. exact handoff prompt 6. what not to do 7. done check.

6. what not to do
Do not reimplement event query, episode query, traversal, detail provenance, or query/list provenance summary.
Do not add semantic search, embeddings, fuzzy matching, OCR/transcription, public write endpoints, ingest changes, correction-model widening, cross-room convenience logic, or any new runtime/API behavior.
Do not invent a next phase or step without repo evidence.

7. done check
Done when either:
a) one exact remaining 2C.1 repo-backed gap is identified and nothing else is widened, or
b) canonical docs clearly mark 2C.1 complete and point to the next approved phase/substep from repo evidence only.
