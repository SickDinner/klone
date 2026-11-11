from __future__ import annotations

from dataclasses import dataclass
import difflib

from .research_memory import ResearchMemory, StoredResearchReport


@dataclass(frozen=True)
class ResearchComparison:
    trace_id: str
    old_version: int
    new_version: int
    old_digest: str
    new_digest: str
    added_citations: tuple[str, ...]
    removed_citations: tuple[str, ...]
    unified_diff: str
    unchanged: bool


def compare_research_versions(
    memory: ResearchMemory, *, trace_id: str,
    old_version: int, new_version: int,
    max_diff_chars: int = 20000,
) -> ResearchComparison:
    """Deterministic, evidence-only comparison of verified public reports.

    No claim of factual correctness is made. Caller must authorize reads.
    """
    if not isinstance(old_version, int) or not isinstance(new_version, int):
        raise ValueError("Version identifiers must be integers")
    if old_version < 1 or new_version < 1 or old_version >= new_version:
        raise ValueError("Expected ascending distinct versions")
    if not isinstance(max_diff_chars, int) or not 1 <= max_diff_chars <= 100000:
        raise ValueError("Invalid diff size")
    old = memory.read(trace_id=trace_id, version=old_version)
    new = memory.read(trace_id=trace_id, version=new_version)
    if old is None or new is None:
        raise ValueError("Report version not found")
    if old.room_id != "public-room" or new.room_id != "public-room":
        raise ValueError("Only public research may be compared")
    delta = "".join(difflib.unified_diff(
        old.markdown.splitlines(keepends=True),
        new.markdown.splitlines(keepends=True),
        fromfile=f"version-{old_version}", tofile=f"version-{new_version}",
        n=2,
    ))
    if len(delta) > max_diff_chars:
        delta = delta[:max_diff_chars] + "\n[Diff truncated]\n"
    old_cites, new_cites = set(old.citations), set(new.citations)
    return ResearchComparison(
        trace_id, old_version, new_version,
        old.content_sha256, new.content_sha256,
        tuple(sorted(new_cites - old_cites)),
        tuple(sorted(old_cites - new_cites)),
        delta, old.content_sha256 == new.content_sha256,
    )
