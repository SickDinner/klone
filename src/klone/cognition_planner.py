"""Pure, deterministic bounded planning laboratory for KLONE.

No tool execution, network, file access, memory writes or authority delegation.
Plans are evaluated against an explicitly supplied toy transition model.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping


@dataclass(frozen=True)
class Action:
    name: str
    energy_cost: float
    information_gain: float
    risk: float

    def __post_init__(self) -> None:
        if not self.name or len(self.name) > 64:
            raise ValueError("Invalid action name")
        for value in (self.energy_cost, self.information_gain, self.risk):
            if not isfinite(value) or not 0 <= value <= 1:
                raise ValueError("Action parameters must be finite values in [0,1]")


@dataclass(frozen=True)
class PlanStep:
    action: str
    energy_after: float
    uncertainty_after: float
    score: float


def plan(
    *,
    energy: float,
    uncertainty: float,
    actions: tuple[Action, ...],
    horizon: int = 3,
    risk_weight: float = 1.0,
) -> dict:
    """Search at most 8 actions and 5 steps. No side effects."""
    if not all(isfinite(v) and 0 <= v <= 1 for v in (energy, uncertainty)):
        raise ValueError("State must be finite and within [0,1]")
    if not isfinite(risk_weight) or not 0 <= risk_weight <= 10:
        raise ValueError("Invalid risk weight")
    if not 1 <= horizon <= 5 or len(actions) > 8:
        raise ValueError("Planning bounds exceeded")
    if len({a.name for a in actions}) != len(actions):
        raise ValueError("Duplicate action name")
    frontier: list[tuple[float, float, float, tuple[PlanStep, ...]]] = [
        (0.0, energy, uncertainty, ())
    ]
    for _ in range(horizon):
        candidates = []
        for total, current_energy, current_uncertainty, path in frontier:
            # Always permit no-op: the system must be able to abstain.
            candidates.append((total, current_energy, current_uncertainty, path))
            for action in actions:
                if action.energy_cost > current_energy:
                    continue
                next_energy = round(current_energy - action.energy_cost, 6)
                next_uncertainty = round(
                    max(0.0, current_uncertainty - action.information_gain), 6
                )
                gain = current_uncertainty - next_uncertainty
                score = round(gain - risk_weight * action.risk -
                              0.1 * action.energy_cost, 6)
                candidates.append((
                    round(total + score, 6), next_energy, next_uncertainty,
                    path + (PlanStep(action.name, next_energy,
                                     next_uncertainty, score),),
                ))
        # Deterministic beam, with fixed upper bound to avoid combinatorial growth.
        frontier = sorted(
            candidates,
            key=lambda x: (-x[0], x[2], -x[1], tuple(s.action for s in x[3])),
        )[:32]
    best = frontier[0]
    return {
        "score": best[0],
        "energy_after": best[1],
        "uncertainty_after": best[2],
        "steps": [step.__dict__ for step in best[3]],
        "experimental": True,
        "actions_executed": 0,
    }


DEFAULT_ACTIONS = (
    Action("observe", 0.08, 0.20, 0.01),
    Action("reflect", 0.05, 0.10, 0.00),
    Action("rest", 0.00, 0.00, 0.00),
)
