"""Deterministic, bounded cognition experiments; no external effects or privilege changes.

This module models *functional* cognitive properties, not subjective experience.
All state is explicit, replayable and scoped to a single in-memory experiment.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from hashlib import sha256
from math import isfinite
import json
from typing import Any


def _bounded(value: float) -> float:
    return round(max(0.0, min(1.0, float(value))), 6)


@dataclass(frozen=True)
class Observation:
    step: int
    signal: float
    source: str = "simulation"

    def __post_init__(self) -> None:
        if self.step < 1 or self.source != "simulation":
            raise ValueError("Only positive simulation steps are accepted")
        if not isfinite(self.signal) or not 0.0 <= self.signal <= 1.0:
            raise ValueError("Signal must be in [0, 1]")


@dataclass
class CognitiveState:
    step: int = 0
    attention: float = 0.5
    uncertainty: float = 0.5
    energy: float = 1.0
    workspace: list[dict[str, Any]] = field(default_factory=list)
    episodes: list[dict[str, Any]] = field(default_factory=list)
    self_model: dict[str, Any] = field(default_factory=lambda: {
        "capabilities": ["simulate", "estimate_uncertainty", "replay"],
        "limitations": ["no external actions", "no consciousness inference"],
        "goal": "evaluate simulated signals",
    })


class CognitionCore:
    """Bounded, deterministic laboratory; does not touch KLONE repositories."""

    def __init__(self, *, workspace_capacity: int = 4, memory_capacity: int = 128,
                 enable_workspace: bool = True, enable_memory: bool = True,
                 enable_self_model: bool = True) -> None:
        if not 1 <= workspace_capacity <= 64 or not 1 <= memory_capacity <= 10000:
            raise ValueError("Invalid capacity")
        self.workspace_capacity = workspace_capacity
        self.memory_capacity = memory_capacity
        self.enable_workspace = enable_workspace
        self.enable_memory = enable_memory
        self.enable_self_model = enable_self_model
        self.state = CognitiveState()
        if not enable_self_model:
            self.state.self_model = {}
        self._inputs: list[Observation] = []

    def step(self, signal: float | None = None) -> dict[str, Any]:
        number = self.state.step + 1
        if signal is None:
            signal = ((number * 37) % 101) / 100
        observation = Observation(step=number, signal=float(signal))
        s = self.state
        previous_attention = s.attention
        s.attention = _bounded(0.65 * s.attention + 0.35 * observation.signal)
        s.uncertainty = _bounded(0.7 * s.uncertainty +
                                 0.3 * abs(observation.signal - s.attention))
        s.energy = _bounded(s.energy - 0.025 + (0.15 if number % 9 == 0 else 0))
        s.step = number
        episode = {
            "step": number, "signal": observation.signal,
            "attention_before": previous_attention, "attention": s.attention,
            "uncertainty": s.uncertainty, "energy": s.energy,
        }
        if self.enable_workspace:
            s.workspace.append({"step": number, "salience": round(
                abs(observation.signal - previous_attention), 6)})
            s.workspace = sorted(s.workspace, key=lambda x: (-x["salience"], x["step"]))[
                :self.workspace_capacity]
        if self.enable_memory:
            s.episodes.append(episode.copy())
            s.episodes = s.episodes[-self.memory_capacity:]
        self._inputs.append(observation)
        return episode

    def run(self, count: int) -> list[dict[str, Any]]:
        if not 0 <= count <= 1000:
            raise ValueError("Count must be between 0 and 1000")
        return [self.step() for _ in range(count)]

    def snapshot(self) -> dict[str, Any]:
        return asdict(self.state)

    def trace_digest(self) -> str:
        payload = json.dumps(
            [asdict(item) for item in self._inputs],
            sort_keys=True, separators=(",", ":"), allow_nan=False,
        )
        return sha256(payload.encode("utf-8")).hexdigest()

    def replay(self) -> "CognitionCore":
        copy = CognitionCore(
            workspace_capacity=self.workspace_capacity,
            memory_capacity=self.memory_capacity,
            enable_workspace=self.enable_workspace,
            enable_memory=self.enable_memory,
            enable_self_model=self.enable_self_model,
        )
        for item in self._inputs:
            copy.step(item.signal)
        assert copy.snapshot() == self.snapshot(), "Replay diverged"
        return copy


def compare_ablations(steps: int = 32) -> dict[str, Any]:
    """Compare functional traces; these scores do NOT measure consciousness."""
    if not 1 <= steps <= 1000:
        raise ValueError("Steps out of range")
    configs = {
        "full": {},
        "no_workspace": {"enable_workspace": False},
        "no_memory": {"enable_memory": False},
        "no_self_model": {"enable_self_model": False},
    }
    result: dict[str, Any] = {}
    for label, options in configs.items():
        core = CognitionCore(**options)
        core.run(steps)
        result[label] = {
            "state": core.snapshot(),
            "digest": core.trace_digest(),
            "replay_matches": core.replay().snapshot() == core.snapshot(),
        }
    return result
