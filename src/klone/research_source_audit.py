"""Deterministic source manifest audit summary for curated public bytes.

This audit checks content equality, not publisher identity or historical truth.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .research_source_manifest import PublicSourceManifest, verify_public_source


@dataclass(frozen=True)
class ManifestAudit:
    verified: tuple[str, ...]
    missing: tuple[str, ...]
    changed: tuple[str, ...]
    unexpected: tuple[str, ...]


def audit_public_sources(
    *, expected: Mapping[str, PublicSourceManifest],
    supplied: Mapping[str, bytes],
) -> ManifestAudit:
    if not isinstance(expected, dict) or not isinstance(supplied, dict):
        raise ValueError("Expected manifest and source dictionaries")
    if len(expected) > 5000 or len(supplied) > 5000:
        raise ValueError("Too many source records")
    if not all(isinstance(k, str) and isinstance(v, PublicSourceManifest)
               and v.source_id == k for k, v in expected.items()):
        raise ValueError("Invalid manifest mapping")
    if not all(isinstance(k, str) and isinstance(v, bytes)
               and len(v) <= 2_000_000 for k, v in supplied.items()):
        raise ValueError("Invalid source bytes")
    verified, missing, changed = [], [], []
    for key in sorted(expected):
        if key not in supplied:
            missing.append(key)
        elif verify_public_source(expected[key], supplied[key]):
            verified.append(key)
        else:
            changed.append(key)
    return ManifestAudit(tuple(verified), tuple(missing), tuple(changed),
                         tuple(sorted(set(supplied) - set(expected))))
