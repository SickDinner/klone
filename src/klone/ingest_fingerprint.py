"""Bounded, offline, streaming ingest fingerprint and duplicate planning.

No file ingestion, DB writes, network, OCR or external embeddings.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import BinaryIO

CHUNK_BYTES = 64 * 1024
MAX_OBJECT_BYTES = 512 * 1024 * 1024


@dataclass(frozen=True)
class IngestFingerprint:
    sha256: str
    byte_length: int
    chunk_count: int


@dataclass(frozen=True)
class IngestPlan:
    action: str
    fingerprint: IngestFingerprint


def fingerprint_stream(stream: BinaryIO, *, max_bytes: int = MAX_OBJECT_BYTES) -> IngestFingerprint:
    """Read a bounded stream incrementally; do not retain its contents."""
    if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or not 0 < max_bytes <= MAX_OBJECT_BYTES:
        raise ValueError("invalid_size_limit")
    digest = sha256()
    total = 0
    chunks = 0
    while True:
        chunk = stream.read(min(CHUNK_BYTES, max_bytes - total + 1))
        if not isinstance(chunk, bytes):
            raise ValueError("binary_stream_required")
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise ValueError("ingest_size_limit")
        digest.update(chunk)
        chunks += 1
    return IngestFingerprint(digest.hexdigest(), total, chunks)


def plan_ingest(fingerprint: IngestFingerprint, *, existing_hashes: frozenset[str]) -> IngestPlan:
    """Read-only duplicate decision; caller must scope hashes to one authorized room."""
    if not isinstance(existing_hashes, frozenset):
        raise ValueError("invalid_duplicate_index")
    if len(fingerprint.sha256) != 64 or fingerprint.byte_length < 0:
        raise ValueError("invalid_fingerprint")
    return IngestPlan("duplicate" if fingerprint.sha256 in existing_hashes else "candidate", fingerprint)
