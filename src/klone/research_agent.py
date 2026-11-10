from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping, Sequence

from .hypervisor_runtime import HypervisorRuntime
from .hypervisor_safe_pipeline import SafeReadPipeline, SafeReadResult


@dataclass(frozen=True)
class ResearchSource:
    source_id: str
    title: str
    text: str
    room_id: str
    classification: str
    reference: str


class ResearchAgent:
    """Deterministic, offline, read-only evidence retriever, not a web crawler or LLM.

    Sources are supplied by a trusted caller. All citations point to actual
    source IDs and references; no generated facts or unsourced assertions.
    """

    def __init__(
        self, *, sources: Sequence[ResearchSource], audit,
        authorize_output, max_output_bytes: int = 65536,
    ) -> None:
        ids = [source.source_id for source in sources]
        if len(ids) != len(set(ids)) or any(
            not s.source_id.strip() or not s.reference.strip()
            or not s.room_id.strip() or not s.title.strip()
            or not s.text.strip() for s in sources
        ):
            raise ValueError("Sources need unique IDs and complete provenance")
        self._sources = tuple(sources)
        self._pipeline = SafeReadPipeline(
            runtime=HypervisorRuntime(),
            handlers={"research.search": self._search_public},
            audit=audit,
            authorize_output=authorize_output,
            max_output_bytes=max_output_bytes,
        )
        self._question = ""

    def search(
        self, *, question: str, room_id: str, actor_role: str,
        trace_id: str, classification_level: str, limit: int = 5,
    ) -> SafeReadResult:
        if not question.strip() or len(question) > 500:
            raise ValueError("Question must contain 1-500 characters")
        if not 1 <= limit <= 10:
            raise ValueError("Result limit must be 1-10")
        # Query is set for the duration of this synchronous call. Instances are
        # not thread safe; callers must create one per request.
        self._question = question
        self._limit = limit
        self._classification = classification_level
        try:
            return self._pipeline.read(
                seam="research.search", room_id=room_id,
                actor_role=actor_role, trace_id=trace_id,
                classification_level=classification_level,
            )
        finally:
            self._question = ""

    def _search_public(self, room_id: str) -> Mapping[str, object]:
        tokens = set(re.findall(r"\w+", self._question.casefold()))
        matches = []
        for source in self._sources:
            if source.room_id != room_id or source.classification != self._classification:
                continue
            haystack = (source.title + " " + source.text).casefold()
            score = sum(1 for token in tokens if token in haystack and len(token) > 2)
            if score:
                matches.append((score, source))
        matches.sort(key=lambda item: (-item[0], item[1].source_id))
        results = [
            {"source_id": source.source_id, "title": source.title,
             "reference": source.reference, "excerpt": source.text[:400],
             "matched_terms": score}
            for score, source in matches[:self._limit]
        ]
        return {
            "question": self._question,
            "results": results,
            "answer": "Evidence excerpts only; no synthesized answer.",
            "source_count": len(results),
        }
