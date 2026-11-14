"""Bounded, stateless council research API; no repository or network access."""
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from .council72 import catalog, deliberate, draft_dispatch, experiment

router = APIRouter(prefix="/api/cognition/council72", tags=["experimental council72"])
Unit = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
Reference = Annotated[str, StringConstraints(min_length=1, max_length=128)]
References = Annotated[list[Reference], Field(max_length=8)]


class Signals(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    evidence_quality: Unit = 0.0
    uncertainty: Unit = 1.0
    risk: Unit = .5
    novelty: Unit = 0.0
    reward: Unit = 0.0
    threat: Unit = 0.0
    social_feedback: Unit = 0.0


class CouncilProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    proposal_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.:-]+$")
    goal: str = Field(min_length=1, max_length=2000)
    classification: Literal["public", "restricted", "sealed"] = "public"
    source_kind: Literal["user_claims", "synthetic_fixture"] = "user_claims"
    signals: Signals = Field(default_factory=Signals)
    ring_evidence: dict[str, References] = Field(default_factory=dict, max_length=8)
    founder_votes: dict[str, Literal["endorse", "oppose", "defer"]] | None = Field(default=None, max_length=8)


class DraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    proposal: CouncilProposal
    king_id: int = Field(ge=1, le=72)
    courier_id: int = Field(ge=1, le=72)
    channel: Literal["forum", "social", "documentation", "research"]
    message: str = Field(min_length=1, max_length=2000)


@router.get("/catalog")
def council_catalog():
    return catalog()


@router.post("/simulate")
def council_simulate(proposal: CouncilProposal):
    try:
        return experiment(proposal.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/draft")
def council_draft(request: DraftRequest):
    try:
        return draft_dispatch(deliberate(request.proposal.model_dump()), king_id=request.king_id,
                              courier_id=request.courier_id, channel=request.channel, message=request.message)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
