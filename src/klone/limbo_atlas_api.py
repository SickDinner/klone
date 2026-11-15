"""Read-only Limbo Atlas E2 API: source catalog and reviewed specialist-ring plans.

External network fetch is deliberately unavailable from HTTP API endpoints.
"""
from __future__ import annotations

from typing import Annotated
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from .limbo_atlas import plan, roster


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
