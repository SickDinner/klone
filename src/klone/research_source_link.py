"""Check that dossier source references have explicit verified byte manifests.

No source acquisition or cryptographic publisher authentication.
"""
from __future__ import annotations

from dataclasses import dataclass

from .research_dossier import ResearchDossier, build_dossier
from .research_source_manifest import PublicSourceManifest, verify_public_source


@dataclass(frozen=True)
class SourceCoverage:
    verified: tuple[str, ...]
    missing: tuple[str, ...]
    mismatched: tuple[str, ...]


def verify_dossier_sources(
    dossier: ResearchDossier,
    manifests: dict[str, PublicSourceManifest],
    source_bytes: dict[str, bytes],
) -> SourceCoverage:
    if not isinstance(dossier, ResearchDossier) or not isinstance(manifests, dict) or not isinstance(source_bytes, dict):
        raise ValueError("Invalid source verification inputs")
    checked = build_dossier(version=dossier.version, hypotheses=dossier.hypotheses,
                            evidence=dossier.evidence)
    if checked.fingerprint != dossier.fingerprint:
        raise ValueError("Dossier integrity mismatch")
    verified, missing, mismatched = [], [], []
    for ref in sorted({e.source_ref for e in dossier.evidence}):
        manifest = manifests.get(ref)
        content = source_bytes.get(ref)
        if manifest is None or content is None:
            missing.append(ref)
        elif manifest.source_id != ref or not verify_public_source(manifest, content):
            mismatched.append(ref)
        else:
            verified.append(ref)
    return SourceCoverage(tuple(verified), tuple(missing), tuple(mismatched))
