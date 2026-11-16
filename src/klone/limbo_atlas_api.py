"""Read-only Limbo Atlas E2 API: source catalog and reviewed specialist-ring plans.

External network fetch is deliberately unavailable from HTTP API endpoints.
"""
from __future__ import annotations

from typing import Annotated
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from .limbo_atlas import plan, roster
from .limbo_memory_bridge import recall
from .limbo_intelligence import analyze
from .api import get_repository
from .repository import KloneRepository


router = APIRouter(prefix="/api/limbo-atlas", tags=["experimental limbo research atlas"])


class AtlasObservation(BaseModel):
    model_config=ConfigDict(extra="forbid", strict=True)
    source_id: Annotated[str, StringConstraints(min_length=1,max_length=64)]
    courier_id: int = Field(ge=1,le=72)
    url: Annotated[str, StringConstraints(min_length=12,max_length=256)]
    title: Annotated[str, StringConstraints(min_length=1,max_length=240)]
    summary: Annotated[str, StringConstraints(min_length=1,max_length=360)]
    published_at: Annotated[str, StringConstraints(min_length=1,max_length=80)] | None = None


class AtlasPlanRequest(BaseModel):
    model_config=ConfigDict(extra="forbid", strict=True)
    observations: list[AtlasObservation] = Field(min_length=1,max_length=48)
    target_ring: int | None = Field(default=None,ge=2,le=8)
    research_question: Annotated[str, StringConstraints(min_length=1,max_length=380)] | None = None


@router.get("/catalog")
def atlas_catalog():
    return roster()


@router.post("/plan")
def atlas_plan(request: AtlasPlanRequest):
    try:
        return plan([item.model_dump() for item in request.observations],
                    ring_id=request.target_ring, question=request.research_question)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/memory/recall")
def atlas_memory_recall(
    q: str = Query(..., min_length=2, max_length=160),
    limit: int = Query(default=12, ge=1, le=30),
    repository: KloneRepository = Depends(get_repository),
):
    """Read owner-accessible public research-room events; no side effects."""
    try:
        return recall(repository.db_path, q, limit=limit)
    except (ValueError, PermissionError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/intelligence")
def atlas_research_intelligence(
    q: str = Query(..., min_length=3, max_length=160),
    limit: int = Query(default=24, ge=1, le=48),
    ring: int | None = Query(default=None, ge=2, le=8),
    repository: KloneRepository = Depends(get_repository),
):
    """Read-only, deterministic E6 research leads from existing KLONE public memories."""
    try:
        return analyze(repository.db_path,q,limit=limit,target_ring=ring)
    except (ValueError,PermissionError) as error:
        raise HTTPException(status_code=422,detail=str(error)) from error
