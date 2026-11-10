from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .hypervisor_safe_pipeline import SafeReadResult


@dataclass(frozen=True)
class ResearchReport:
    trace_id: str
    room_id: str
    title: str
    markdown: str
    citations: tuple[str, ...]


def build_research_report(result: SafeReadResult) -> ResearchReport:
    """Render a deterministic evidence-only report from an authorized read result.

    The report never infers conclusions beyond source excerpts. Caller must
    ensure the report is released only to the authorized request principal.
    """
    payload: Mapping[str, Any] = result.payload
    question = payload.get("question")
    entries = payload.get("results")
    if not isinstance(question, str) or not question.strip():
        raise ValueError("Research result has no valid question")
    if not isinstance(entries, list) or len(entries) > 10:
        raise ValueError("Research result has invalid sources")
    if payload.get("source_count") != len(entries):
        raise ValueError("Research source count mismatch")
    lines = ["# Tutkimusraportti", "", "## Tutkimuskysymys", "",
             question.replace("\\", "\\\\").replace("<", "&lt;"), "",
             "## Lähdehavainnot", ""]
    citations: list[str] = []
    for index, entry in enumerate(entries, 1):
        if not isinstance(entry, dict):
            raise ValueError("Malformed research citation")
        source_id, title, reference, excerpt = (
            entry.get("source_id"), entry.get("title"),
            entry.get("reference"), entry.get("excerpt"),
        )
        if any(not isinstance(value, str) or not value.strip()
               for value in (source_id, title, reference, excerpt)):
            raise ValueError("Incomplete research citation")
        if reference in citations:
            raise ValueError("Duplicate research citation")
        citations.append(reference)
        safe_title = title.replace("\n", " ").replace("<", "&lt;")
        safe_excerpt = excerpt.replace("<", "&lt;")
        safe_ref = reference.replace("<", "&lt;")
        lines.extend([f"### {index}. {safe_title}", "",
                      safe_excerpt, "", f"Lähde: `{safe_ref}`", ""])
    if not entries:
        lines.extend(["Aineistosta ei löytynyt hakuehtoihin sopivia havaintoja.", ""])
    lines.extend(["## Rajaukset", "",
                  "Raportti sisältää vain aineistosta poimitut otteet. "
                  "Se ei vahvista väitteiden paikkansapitävyyttä eikä tee itsenäisiä johtopäätöksiä.",
                  "", f"Jäljitystunniste: `{result.trace_id}`"])
    return ResearchReport(result.trace_id, result.room_id, question,
                          "\n".join(lines), tuple(citations))
