# Phase A1.10: scoped implementation approval

Status: **implementation approved by owner request of 2026-11-11**, pending review and passing tests before merge. This document records the user's explicit request to implement all proposed A1.10 work; it does **not** approve other phase expansions.

Scope: Memory Explorer selection lifecycle safety, stale data clearing, async request guards, read-only provenance and context presentation, room-scoped change preview where identifiers match, and browser smoke coverage.

Non-goals: Constitution writes/live routing/approval workflow, Art Lab OCR/embeddings/batch clustering, Genomics raw intake/annotation, deeper ingest/OCR/transcription, new memory writes or new privileges. These remain separately gated.

Safety: preserve room and role guards, escape all untrusted data, maintain bounded results and audit integrity. Code is subject to CI and human review before merge.
