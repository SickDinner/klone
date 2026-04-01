# Klone Parser and Interface Roadmap

Status: broad architect roadmap, not canonical by itself  
Date: 2026-04-01

This file is the larger product roadmap behind the current repo state.  
Canonical approved scope still lives in:

- `docs/ROADMAP.md`
- `docs/PROJECT_STATUS.md`
- `docs/HANDOFF_CURRENT.md`

## Product direction

Turn Klone from a bounded shell collection into one coherent clone workstation where the same UI can:

- ingest and inspect files
- analyze dialogue and autobiographical history
- render a conversational clone
- inspect visual/media structure
- project memories into boards, places, and timelines
- expose constitution, governance, and future supervised model-training loops

## North-star interface

The Mission Control UI should eventually unify six operator surfaces:

1. `Corpus and parser workbench`
   Messenger, ChatGPT, journals, notes, email, OCR text, transcripts, and attachment metadata.
2. `People and relationship graph`
   reviewable people cards, contact strength, family/friend/work labels, uncertainty, and evidence chains.
3. `Timeline and autobiography`
   year/month/day episodes, major eras, routines, places, projects, and relationship arcs.
4. `Visual and media lab`
   current art metrics, 2.5D depth maps, later segmentation, OCR, face clusters, style drift, and gallery compare.
5. `Clone interaction room`
   normal chat with bounded evidence, model mode controls, review queue, and eventually supervised clone fine-tuning hooks.
6. `Governance and constitution`
   rooms, approvals, training corpora selection, evaluation gates, and slow-cycle parameter changes.

## Suggested next expansion lanes

These are the next meaningful families after the newly completed `V1.3` depth-map shell.

### Lane A: parser unification

Goal:
Make all personal source types flow through one visible parser workbench instead of separate narrow tools.

Suggested substeps:

- `2B.9 reviewable relationship candidates`
  turn corpus priors into reviewable people/relationship candidates without auto-committing durable labels
- `2B.10 autobiographical timeline shell`
  fuse dialogue activity, datasets, and existing memory evidence into eras, bursts, and continuity markers
- `G2 multimodal parser queue`
  stage OCR, transcript, document-text, and attachment-side extraction jobs behind the same governed intake model
- `G2.1 OCR shell`
  image/document text extraction with visible confidence and page provenance
- `G2.2 transcription shell`
  audio/video transcript extraction with speaker hints and evidence timestamps

### Lane B: clone quality

Goal:
Move from bounded answers toward a recognizably useful clone while keeping supervision explicit.

Suggested substeps:

- `2B.11 reviewable self-model priors`
  stable but reviewable style, habits, preference, and relationship priors
- `2B.12 clone memory seeding handoff`
  explicit operator-reviewed move from corpus priors into governed memory candidates
- `2E.2 constitution write proposal shell`
  review queue for slow-cycle parameter proposals before any live influence
- `2E.3 training corpus registry`
  define which rooms and datasets may participate in future tuning/eval
- `2F.1 circadian shell`
  quiet hours, consolidation windows, maintenance cycles, and routing posture

### Lane C: visual intelligence

Goal:
Keep growing the art/media lab without jumping straight into opaque profiling.

Suggested substeps:

- `V1.4 reviewable image segmentation shell`
  transient masks and foreground-background separation without asset writeback
- `V1.5 OCR-aware visual shell`
  text-bearing image inspection once OCR exists in the parser lane
- `V1.6 gallery compare board`
  side-by-side boards for art, screenshots, photos, and document visuals
- `V1.7 face and person cluster review`
  review-only identity clustering over personal images with strict approval and uncertainty
- `V1.8 motion and video shell`
  keyframes, shots, activity bands, and attachment linking

### Lane D: world and place memory

Goal:
Bind personal data to places, rooms, and recurring environments.

Suggested substeps:

- `S1.2 place timeline shell`
  when and how locations recur across datasets and memories
- `S1.3 environment reconstruction shell`
  layout cues from images, paths, and asset groupings
- `S1.4 world-memory review queue`
  operator review of clusters, anchors, and place labels

### Lane E: supervised training and evaluation

Goal:
Make later clone tuning deliberate instead of accidental.

Suggested substeps:

- `T1.1 clone eval harness`
  compare local bounded answer vs GPT rendering vs later fine-tuned models
- `T1.2 training example builder`
  review and export supervised examples from approved evidence
- `T1.3 preference and style evals`
  score how well the clone matches known style and relationship facts without hallucination
- `T1.4 governed fine-tuning jobs`
  approved external training runs only from explicitly selected corpora

## Immediate practical order

If the goal is to make Klone materially more useful fast, the best next order is:

1. `2B.9 reviewable relationship candidates`
2. `2B.10 autobiographical timeline shell`
3. `G2.1 OCR shell`
4. `G2.2 transcription shell`
5. `V1.4 segmentation shell`
6. `2B.12 clone memory seeding handoff`
7. `T1.1 clone eval harness`

## What this roadmap intentionally avoids

- unsupervised full-autonomy claims
- silent memory mutation
- hidden embeddings-first behavior everywhere
- personality or mental-health profiling from weak evidence
- direct model self-editing
- ungoverned fine-tuning from intimate corpora

## Current repo anchor

As of this document, the concrete implemented addition is:

- `V1.3 read-only 2.5D depth map shell`

That means the broader roadmap can now build on:

- ingest spine
- dialogue corpus shell
- clone chat shell
- memory explorer
- constitution shell
- hybrid/world-memory projections
- art metrics and comparison
- transient local depth mapping in Mission Control
