"""Public-only, read-only Knowledge Atlas endpoints.

The API never starts a Wikipedia download or an LLM call. It exposes
a separate public corpus, not the private Memory Core or its audit data.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from .knowledge_atlas import Atlas, AtlasError
from .knowledge_atlas_bridge import read_only_council_packet
from .knowledge_atlas_topics import LANGUAGES, plan, profiles

router = APIRouter(prefix="/api/knowledge-atlas", tags=["knowledge-atlas"])

DEFAULT_ROOT = Path.home() / "klone-var/knowledge-atlas"


def _installed_atlas():
    # Avoid creating a new database while serving read-only GETs.
    if not (DEFAULT_ROOT / "wikipedia.sqlite3").is_file():
        raise HTTPException(status_code=404, detail="Wikipedia knowledge atlas not initialized")
    return Atlas(DEFAULT_ROOT)


@router.get("/plan")
def get_plan():
    return plan()


@router.get("/members")
def get_members():
    return {"kind": "council72-public-member-topics", "members": profiles(),
            "memory_write": False}


@router.get("/members/{member_id}")
def get_member(member_id: int):
    profile = next(
        (p for p in profiles() if p["member_id"] == member_id), None
    )
    if profile is None:
        raise HTTPException(status_code=404, detail="Council72 role not found")
    return profile


@router.get("/status")
def get_status():
    if not (DEFAULT_ROOT / "wikipedia.sqlite3").is_file():
        return {
            "kind": "klone-wikimedia-knowledge-atlas-v1",
            "installed": False, "distinct_article_count": 0,
            "target_distinct_articles": 72_000,
            "network_requests": 0, "memory_write": False,
        }
    with _installed_atlas() as atlas:
        value = atlas.state()
        value["installed"] = True
        value["network_requests"] = 0
        return value


@router.get("/search")
def get_search(q: str = Query(min_length=2, max_length=250),
               member_id: int | None = None,
               language: str | None = None,
               limit: int = Query(default=8, ge=1, le=30)):
    if language is not None and language not in LANGUAGES:
        raise HTTPException(status_code=400, detail="unsupported language")
    try:
        with _installed_atlas() as atlas:
            return atlas.search(
                q, member_id=member_id, language=language, limit=limit
            )
    except AtlasError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@router.get("/council/{ring_id}")
def get_council_context(ring_id: int,
                        question: str = Query(min_length=2, max_length=200),
                        language: str | None = None):
    if language is not None and language not in LANGUAGES:
        raise HTTPException(status_code=400, detail="unsupported language")
    try:
        with _installed_atlas() as atlas:
            return read_only_council_packet(
                atlas, ring_id=ring_id, question=question,
                language=language, per_member=2
            )
    except AtlasError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
