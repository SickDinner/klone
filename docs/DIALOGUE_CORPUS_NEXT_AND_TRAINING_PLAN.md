# Dialogue Corpus Next And Training Plan

Last updated: 2026-04-01

## Current baseline

- `Phase 2B.6` gives Klone read-only aggregate analysis over Messenger and ChatGPT exports already present on disk.
- `Phase 2B.7` adds a bounded parser and local `klone` CLI so the owner can already test direct questions against aggregate dialogue evidence.
- The system still does **not** write raw messages into memory, does **not** do raw semantic retrieval, and does **not** infer psychology or relationship truth from chat logs alone.

## Immediate next build steps

1. Reviewable relationship candidate extraction
- materialize candidate counterparts, group clusters, and recency bands as review rows rather than automatic truth labels
- keep every candidate linked back to exact export/thread evidence
- add explicit owner approval before any candidate becomes durable clone state

2. Dialogue ingest handoff into `intimate`
- convert approved dialogue candidates into governed ingest artifacts instead of bypassing the existing room model
- preserve source lineage from export root -> thread -> aggregate candidate -> approved memory seed
- keep memory writes replayable and reversible

3. Richer counterpart lookup
- expand named lookup beyond direct-thread counters into reviewable thread summaries, recency windows, and cross-section presence
- keep the output bounded and citeable
- block free-form narrative synthesis until retrieval provenance is explicit

4. Evaluation harness for `/klone`
- add gold questions for strongest ties, timeline coverage, top groups, style priors, and specific-name lookup
- store expected factual answers and allowed uncertainty language
- fail the parser if it overclaims beyond visible evidence

## Training plan

### Stage 1: Retrieval-first clone bootstrapping

- do **not** fine-tune a model first
- instead, build a retrieval-backed clone shell where `/klone` always answers from governed evidence packages
- training target at this stage is the parser, ranking, citation, and gating behavior, not persona imitation

### Stage 2: Approved style priors

- derive safe style priors from owner-sent text only after approval
- keep style features aggregate and reviewable: sentence length bands, question rate, link rate, attachment rate, recurring lexical preferences
- use these priors to shape answer tone only after factual retrieval is already stable

### Stage 3: Supervised clone-answer dataset

- create a curated training set of owner-approved question/answer pairs grounded in dialogue evidence
- separate factual relationship questions from voice/style questions
- every example should carry provenance, room classification, and an approval state
- exclude unstable, defamatory, medical, or clinical-style labels from the supervised set

### Stage 4: Fine-tuning or adapter training

- only after retrieval and evaluation are stable
- prefer a small adapter or local fine-tune over baking raw private dialogue into a monolithic model
- train for response shaping and preferred framing, not for replacing evidence retrieval
- keep the deployed answer path retrieval-first so the model cannot silently invent unsupported relationship facts

### Stage 5: Red-team and safety verification

- probe for overclaiming, romantic/clinical projection, false certainty, and unsupported summaries of named people
- verify that unsupported questions stay unsupported
- verify that the model does not expose raw intimate text outside approved evidence windows

## What `/klone` should become

Short term:
- a bounded local parser over approved dialogue evidence
- good at “who do I talk to most”, “what does my network look like”, “what does my style look like”, and “what does this corpus contain about X”

Mid term:
- a governed clone interface that answers from memory, media, calendar, notes, and dialogue together
- still source-linked and room-scoped

Later:
- a retrieval-backed personal model with approved style adaptation
- not a raw dump of private chats into an unconstrained chatbot

## Non-goals for the next step

- no automatic durable relationship labels
- no psychology or sentiment classifier over private chats
- no embeddings-first semantic search over raw intimate logs
- no direct raw-message training dump into a base model
- no write-enabled autonomous clone loop
