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
        if not callable(audit) or not callable(authorize_output):
            raise ValueError("Audit and output policy callbacks are required")
        if max_output_bytes < 1:
            raise ValueError("Output limit must be positive")
        ids = [source.source_id for source in sources]
        if len(ids) != len(set(ids)) or any(
            not s.source_id.strip() or not s.reference.strip()
            or not s.room_id.strip() or not s.title.strip()
            or not s.text.strip() for s in sources
        ):
            raise ValueError("Sources need unique IDs and complete provenance")
        self._sources = tuple(sources)
        self._audit = audit
        self._authorize_output = authorize_output
        self._max_output_bytes = max_output_bytes

    def search(
        self, *, question: str, room_id: str, actor_role: str,
        trace_id: str, classification_level: str, limit: int = 5,
    ) -> SafeReadResult:
        if not isinstance(question, str) or not question.strip() or len(question) > 500:
            raise ValueError("Question must contain 1-500 characters")
        if not 1 <= limit <= 10:
            raise ValueError("Result limit must be 1-10")
        def search_room(allowed_room: str) -> Mapping[str, object]:
            return self._search_room(
                question=question, room_id=allowed_room,
                classification_level=classification_level, limit=limit,
            )

        pipeline = SafeReadPipeline(
            runtime=HypervisorRuntime(),
            handlers={"research.search": search_room},
            audit=self._audit,
            authorize_output=self._authorize_output,
            max_output_bytes=self._max_output_bytes,
        )
        return pipeline.read(
            seam="research.search", room_id=room_id,
            actor_role=actor_role, trace_id=trace_id,
            classification_level=classification_level,
        )

    def _search_room(
        self, *, question: str, room_id: str,
        classification_level: str, limit: int,
    ) -> Mapping[str, object]:
        tokens = set(re.findall(r"\w+", question.casefold()))
        matches = []
        for source in self._sources:
            if source.room_id != room_id or source.classification != classification_level:
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
            for score, source in matches[:limit]
        ]
        return {
            "question": question,
            "results": results,
            "answer": "Evidence excerpts only; no synthesized answer.",
            "source_count": len(results),
        }
