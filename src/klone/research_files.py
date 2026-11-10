from __future__ import annotations

from pathlib import Path
import hashlib
from typing import Sequence

from .research_agent import ResearchSource


def load_research_texts(
    *, root: Path, relative_paths: Sequence[str],
    room_id: str, classification: str = "public",
    max_files: int = 25, max_file_bytes: int = 65536,
    max_total_bytes: int = 262144,
) -> tuple[ResearchSource, ...]:
    """Load explicitly selected UTF-8 .txt/.md files from a trusted local root.

    No recursive crawling, symlinks, absolute paths or network resources.
    The caller controls root and must authorize access to it before invoking.
    """
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Root must be a real directory")
    if not room_id.strip() or classification not in {"public", "personal", "intimate", "restricted_bio"}:
        raise ValueError("Invalid room or classification")
    if max_files < 1 or max_file_bytes < 1 or max_total_bytes < 1:
        raise ValueError("File limits must be positive")
    if any(not isinstance(item, str) for item in relative_paths):
        raise ValueError("Paths must be strings")
    if len(relative_paths) > max_files or len(set(relative_paths)) != len(relative_paths):
        raise ValueError("Too many or duplicate paths")
    base = root.resolve(strict=True)
    total = 0
    sources: list[ResearchSource] = []
    for rel in relative_paths:
        if not isinstance(rel, str) or not rel or "\\" in rel:
            raise ValueError("Invalid relative path")
        requested = Path(rel)
        if requested.is_absolute() or any(part in (".", "..") for part in requested.parts):
            raise ValueError("Absolute or traversing path rejected")
        if requested.suffix.lower() not in {".txt", ".md"}:
            raise ValueError("Only .txt and .md files are supported")
        candidate = base / requested
        if any(node.is_symlink() for node in (candidate, *candidate.parents) if node != base and base in node.parents):
            raise ValueError("Symlink path rejected")
        resolved = candidate.resolve(strict=True)
        if not resolved.is_relative_to(base) or not resolved.is_file():
            raise ValueError("Path outside research root or not a file")
        size = resolved.stat().st_size
        if size > max_file_bytes or total + size > max_total_bytes:
            raise ValueError("Research corpus byte limit exceeded")
        # Explicitly bounded read; fail if a file grows between stat and read.
        with resolved.open("rb") as handle:
            raw = handle.read(max_file_bytes + 1)
        if len(raw) > max_file_bytes:
            raise ValueError("Research file grew beyond byte limit")
        total += len(raw)
        text = raw.decode("utf-8")
        if not text.strip():
            continue
        digest = hashlib.sha256(raw).hexdigest()
        sources.append(ResearchSource(
            source_id=digest + ":" + rel, title=requested.name,
            text=text, room_id=room_id, classification=classification,
            reference=f"local:{rel}#sha256={digest}",
        ))
    return tuple(sources)
