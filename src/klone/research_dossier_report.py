"""Safe, deterministic Markdown report for curated public dossier metadata.

Human-supplied stances are not verified scientific conclusions.
"""
from __future__ import annotations

from .research_dossier import ResearchDossier, build_dossier
from .research_dossier_review import review_dossier


def _safe(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("Report fields must be strings")
    return (value.replace("\\", "\\\\").replace("|", "\\|")
            .replace("\r", " ").replace("\n", " ")
            .replace("<", "&lt;").replace(">", "&gt;"))


def render_dossier_markdown(dossier: ResearchDossier) -> str:
    """Render traceable source references without fetching external content."""
    checked = build_dossier(version=dossier.version, hypotheses=dossier.hypotheses,
                            evidence=dossier.evidence)
    if checked.fingerprint != dossier.fingerprint:
        raise ValueError("Dossier integrity mismatch")
    review = review_dossier(dossier)
    lines = [
        "# KLONE public research dossier",
        "",
        f"Version: {dossier.version}",
        f"Fingerprint: `{dossier.fingerprint}`",
        "",
        "Human review required. Evidence stances are supplied by the researcher,",
        "not verified source truth, calibrated probability or kinship proof.",
        "",
        "## Hypotheses",
        "",
        "| ID | Statement |",
        "| --- | --- |",
    ]
    for h in sorted(dossier.hypotheses, key=lambda x: x.hypothesis_id):
        lines.append(f"| {_safe(h.hypothesis_id)} | {_safe(h.statement)} |")
    lines.extend(["", "## Evidence", "",
                  "| ID | Source reference | Hypothesis | Stance | Quality | Dependency |",
                  "| --- | --- | --- | --- | --- | --- |"])
    for e in sorted(dossier.evidence, key=lambda x: x.evidence_id):
        lines.append("| " + " | ".join(_safe(v) for v in (
            e.evidence_id, e.source_ref, e.hypothesis_id, e.stance,
            e.quality, e.dependency_group)) + " |")
    lines.extend(["", "## Review flags", "",
                  f"Contradictions: {', '.join(map(_safe, review.contradictions)) or 'none'}",
                  f"Unresolved: {', '.join(map(_safe, review.unresolved)) or 'none'}",
                  f"Dependency collisions: {', '.join(map(_safe, review.dependency_collisions)) or 'none'}",
                  ""])
    return "\n".join(lines)
