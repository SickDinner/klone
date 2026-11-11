"""Content-addressed manifests for explicitly supplied public source bytes.

Digest proves byte equality only, not authenticity, licensing or factual truth.
No network or filesystem access is performed.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256


@dataclass(frozen=True)
class PublicSourceManifest:
    source_id: str
    media_type: str
    byte_length: int
    sha256_hex: str


def manifest_public_source(*, source_id: str, content: bytes,
                           media_type: str = "text/plain") -> PublicSourceManifest:
    if not isinstance(source_id, str) or not 1 <= len(source_id) <= 256 or not source_id.strip():
        raise ValueError("Invalid source identifier")
    if not isinstance(content, bytes) or len(content) > 2_000_000:
        raise ValueError("Invalid source bytes or size")
    if media_type not in ("text/plain", "text/markdown", "application/json"):
        raise ValueError("Unsupported public source media type")
    return PublicSourceManifest(source_id, media_type, len(content), sha256(content).hexdigest())


def verify_public_source(manifest: PublicSourceManifest, content: bytes) -> bool:
    if not isinstance(manifest, PublicSourceManifest):
        raise ValueError("Invalid source manifest")
    if not isinstance(content, bytes):
        return False
    return (manifest_public_source(source_id=manifest.source_id, content=content,
                                   media_type=manifest.media_type) == manifest)
