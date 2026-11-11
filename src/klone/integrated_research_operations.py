"""Read-only preview and inspection for KLONE public research dossiers.

Preview verifies explicitly supplied source bytes before any database access.
Inspect reads an existing immutable dossier version; sources are not stored
in the dossier database, so inspection cannot independently reverify bytes.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .research_dossier_import import import_public_dossier_json
from .research_dossier_review import review_dossier, DossierReview
from .research_dossier_workflow import read_research_dossier
from .research_source_manifest import PublicSourceManifest
from .research_verified_report import publish_verified_dossier_report, GatedReport
from .research_dossier_report import render_dossier_markdown


@dataclass(frozen=True)
class ResearchPreview:
    review: DossierReview
    report: GatedReport


def preview_public_research(
    *, json_text: str, manifests: dict[str, PublicSourceManifest],
    source_bytes: dict[str, bytes],
) -> ResearchPreview:
    dossier = import_public_dossier_json(json_text)
    report = publish_verified_dossier_report(
        dossier=dossier, manifests=manifests, source_bytes=source_bytes)
    return ResearchPreview(review_dossier(dossier), report)


@dataclass(frozen=True)
class ResearchInspection:
    dossier_id: str
    version: int
    review: DossierReview
    markdown: str


def inspect_public_research(
    *, database_path: Path, dossier_id: str, version: int,
) -> ResearchInspection:
    dossier = read_research_dossier(
        database_path=database_path, dossier_id=dossier_id, version=version)
    return ResearchInspection(
        dossier_id=dossier_id, version=version, review=review_dossier(dossier),
        markdown=render_dossier_markdown(dossier))
