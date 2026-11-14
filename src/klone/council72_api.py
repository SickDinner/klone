"""Bounded council simulations plus an explicit, audited public memory count probe."""
from typing import Annotated, Literal
from sqlite3 import Error as SQLiteError

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from .council72 import catalog, deliberate, draft_dispatch, experiment
from .council72_session import run_session
from .council72_review import review_session
from .council72_briefing import build_briefing
from .council72_contract import register_contract
from .api import get_repository
from .council72_memory import public_memory_observation
from .hypervisor_dispatch import DispatchDenied
from .repository import KloneRepository

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


Identifier = Annotated[str, StringConstraints(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.:-]+$")]


class SessionObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: Identifier
    courier_id: int = Field(ge=1, le=72)
    source_ref: str = Field(min_length=1, max_length=256)
    source_group: Identifier
    claim_key: Identifier
    stance: Literal["supports", "contradicts", "unknown"]
    summary: str = Field(min_length=1, max_length=512)
    classification: Literal["public", "restricted", "sealed"] = "public"
    signals: Signals = Field(default_factory=Signals)
    supersedes: Identifier | None = None
    observed_at: str | None = Field(default=None, min_length=1, max_length=64)


class SessionDispatch(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    king_id: int = Field(ge=1, le=72)
    courier_id: int = Field(ge=1, le=72)
    channel: Literal["forum", "social", "documentation", "research"]
    message: str = Field(min_length=1, max_length=2000)


class SessionStep(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    observations: list[SessionObservation] = Field(min_length=1, max_length=32)
    founder_votes: dict[str, Literal["endorse", "oppose", "defer"]] | None = Field(default=None, max_length=8)
    dispatches: list[SessionDispatch] = Field(default_factory=list, max_length=8)


class SessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    session_id: Identifier
    goal: str = Field(min_length=1, max_length=2000)
    classification: Literal["public", "restricted", "sealed"] = "public"
    source_kind: Literal["user_claims", "synthetic_fixture"] = "user_claims"
    steps: list[SessionStep] = Field(min_length=1, max_length=8)


@router.post("/session")
def council_session(request: SessionRequest):
    try:
        return run_session(request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    session: SessionRequest
    domain_states: dict[str, Literal["passed", "failed", "pending", "unverified", "not_applicable"]] | None = Field(default=None, max_length=12)
    budget_minutes: int = Field(default=60, ge=1, le=480)
    max_tasks: int = Field(default=8, ge=1, le=32)
    max_source_groups: int = Field(default=16, ge=1, le=32)


@router.post("/review")
def council_review(request: ReviewRequest):
    try:
        return review_session(run_session(request.session.model_dump()),
            domain_states=request.domain_states, budget_minutes=request.budget_minutes,
            max_tasks=request.max_tasks, max_source_groups=request.max_source_groups)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/briefing")
def council_briefing(request: ReviewRequest):
    try:
        session = run_session(request.session.model_dump())
        options = request.model_dump(exclude={"session"})
        return build_briefing(review_session(session, **options))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


class MemoryObservationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    limit: int = Field(default=50, ge=1, le=200)


class ContractCriterion(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: Identifier
    claim_key: Identifier
    domain: str = Field(min_length=1, max_length=32)
    stage: Literal["syntax", "cognition", "full", "local_deploy"]
    environment: Literal["work", "android"]
    min_passed: int = Field(ge=0, le=1000000)


class ContractSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    contract_id: Identifier
    goal: str = Field(min_length=1, max_length=2000)
    target_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    classification: Literal["public", "restricted", "sealed"]
    criteria: list[ContractCriterion] = Field(min_length=1, max_length=16)


@router.post("/contract")
def council_contract(request: ContractSpec):
    try:
        return register_contract(request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/memory-observation")
def council_memory_observation(request: MemoryObservationRequest,
                               repository: KloneRepository = Depends(get_repository)):
    try:
        return public_memory_observation(repository, limit=request.limit)
    except DispatchDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (OSError, SQLiteError) as exc:
        raise HTTPException(status_code=503, detail="Muistihavainnon auditointi ei valmistunut.") from exc


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
