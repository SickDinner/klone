"""Read-only public-source intake previews for existing Council 72 Limbo couriers.

No HTTP fetching from this router and no external posting, credential, or
authenticated Memory Core access. Request body is untrusted public metadata.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from .limbo_external import agents, analyze_documents, draft_question, sources


router = APIRouter(prefix="/api/limbo-external", tags=["experimental limbo external"])
Text = Annotated[str, StringConstraints(min_length=1, max_length=512)]
Url = Annotated[str, StringConstraints(min_length=10, max_length=256)]


class PublicDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    source_id: Annotated[str, StringConstraints(min_length=1, max_length=60)]
    courier_id: int = Field(ge=1, le=72)
    url: Url
    title: Annotated[str, StringConstraints(min_length=1, max_length=240)]
    summary: Annotated[str, StringConstraints(min_length=1, max_length=360)]
    published_at: Annotated[str, StringConstraints(min_length=1, max_length=80)] | None = None


class PreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    goal: Annotated[str, StringConstraints(min_length=1, max_length=2000)] = (
        "Julkisen maailman havaintojen kriittinen tutkiminen"
    )
    documents: list[PublicDocument] = Field(min_length=1, max_length=48)


class QuestionDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    courier_id: int = Field(ge=1, le=72)
    source_id: Annotated[str, StringConstraints(min_length=1, max_length=60)]
    question: Annotated[str, StringConstraints(min_length=1, max_length=380)]


@router.get("/agents")
def limbo_agents() -> dict:
    return {
        "agents": agents(),
        "source_classification": "public",
        "external_actions": False,
        "posting": False,
        "network_fetch_from_api": False,
        "memory_write_enabled": False,
    }


@router.get("/sources")
def limbo_public_sources() -> dict:
    return {
        "sources": sources(),
        "network_fetch_from_api": False,
        "manual_fetch_available": True,
        "external_actions": False,
    }


@router.post("/preview")
def limbo_preview(request: PreviewRequest) -> dict:
    try:
        return analyze_documents(
            [d.model_dump() for d in request.documents],
            goal=request.goal,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/question-draft")
def limbo_question_draft(request: QuestionDraftRequest) -> dict:
    try:
        return draft_question(**request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
