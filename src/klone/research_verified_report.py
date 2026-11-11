"""Fail-closed report publication gate for explicitly supplied source bytes.

A passed gate verifies byte equality only. Authorization and publisher
authenticity must be established separately by trusted KLONE services.
"""
from __future__ import annotations

from dataclasses import dataclass

from .research_dossier import ResearchDossier
from .research_dossier_report import render_dossier_markdown
from .research_source_manifest import PublicSourceManifest, verify_public_source


@dataclass(frozen=True)
class GatedReport:
    markdown: str
    verified_source_ids: tuple[str, ...]


def publish_verified_dossier_report(
    *, dossier: ResearchDossier,
    manifests: dict[str, PublicSourceManifest],
    source_bytes: dict[str, bytes],
) -> GatedReport:
    if not isinstance(dossier, ResearchDossier) or not isinstance(manifests, dict) or not isinstance(source_bytes, dict):
        raise ValueError("Invalid report publication inputs")
    # Validate dossier and fingerprint even if no evidence is present.
    markdown = render_dossier_markdown(dossier)
    required = {e.source_ref for e in dossier.evidence}
    if len(required) > 5000:
        raise ValueError("Too many source references")
    verified = []
    for source_id in sorted(required):
        manifest = manifests.get(source_id)
        content = source_bytes.get(source_id)
        if (manifest is None or content is None or
            manifest.source_id != source_id or
            not verify_public_source(manifest, content)):
            raise ValueError("Missing or mismatched source: " + source_id[:128])
        verified.append(source_id)
    return GatedReport(markdown, tuple(verified))
