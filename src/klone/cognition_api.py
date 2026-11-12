"""Stateless experimental cognition endpoints, isolated from KLONE memory writes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from .cognition_core import CognitionCore, compare_ablations
from .api import get_repository
from .repository import KloneRepository
from .cognition_memory import probe_memory
from .cognition_planner import DEFAULT_ACTIONS, plan
from .cognition_learning import LearningConfig, compare_learning

router = APIRouter(prefix="/api/cognition", tags=["experimental cognition"])


class SimulationRequest(BaseModel):
    steps: int = Field(default=10, ge=0, le=200)
    workspace_capacity: int = Field(default=4, ge=1, le=64)
    memory_capacity: int = Field(default=128, ge=1, le=10000)
    enable_workspace: bool = True
    enable_memory: bool = True
    enable_self_model: bool = True


@router.get("/capabilities")
def capabilities() -> dict:
    return {
        "experimental": True,
        "consciousness_claim": False,
        "persistence": "none",
        "external_actions": False,
        "memory_access": False,
        "permissions": "none granted",
        "max_steps": 200,
    }


@router.post("/simulate")
def simulate(request: SimulationRequest) -> dict:
    core = CognitionCore(
        workspace_capacity=request.workspace_capacity,
        memory_capacity=request.memory_capacity,
        enable_workspace=request.enable_workspace,
        enable_memory=request.enable_memory,
        enable_self_model=request.enable_self_model,
    )
    trace = core.run(request.steps)
    return {
        "experimental": True,
        "trace": trace,
        "state": core.snapshot(),
        "trace_digest": core.trace_digest(),
        "replay_matches": core.replay().snapshot() == core.snapshot(),
    }


@router.post("/ablations")
def ablations(request: SimulationRequest) -> dict:
    if request.steps < 1:
        return {"experimental": True, "results": {}}
    return {"experimental": True, "results": compare_ablations(request.steps)}


@router.get("/memory-probe")
def memory_probe(
    room_id: str = Query(..., min_length=1),
    limit: int = Query(default=50, ge=1, le=200),
    repository: KloneRepository = Depends(get_repository),
) -> dict:
    """Authorized bounded summary; no raw memory content is returned."""
    return probe_memory(repository, room_id=room_id, limit=limit).public_summary()


class PlanRequest(BaseModel):
    energy: float = Field(default=1.0, ge=0, le=1, allow_inf_nan=False)
    uncertainty: float = Field(default=0.5, ge=0, le=1, allow_inf_nan=False)
    horizon: int = Field(default=3, ge=1, le=5)
    risk_weight: float = Field(default=1.0, ge=0, le=10, allow_inf_nan=False)


@router.post("/plan")
def planning_experiment(request: PlanRequest) -> dict:
    """Pure planning only: returns suggestions, never executes actions."""
    return plan(energy=request.energy, uncertainty=request.uncertainty,
                actions=DEFAULT_ACTIONS, horizon=request.horizon,
                risk_weight=request.risk_weight)


class LearningRequest(BaseModel):
    steps: int = Field(default=64, ge=1, le=500)
    seed: int = Field(default=72, ge=0, le=4294967295)
    learning_rate: float = Field(default=0.2, ge=0, le=1, allow_inf_nan=False)
    initial_prediction: float = Field(default=0.5, ge=0, le=1, allow_inf_nan=False)


@router.post("/learn")
def learning_experiment(request: LearningRequest) -> dict:
    """Stateless seeded prediction experiment with a no-learning baseline."""
    return compare_learning(LearningConfig(**request.model_dump()))
