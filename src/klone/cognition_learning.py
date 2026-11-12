"""Bounded, deterministic, in-memory predictive learning experiments."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from hashlib import sha256
from math import isfinite
import json


@dataclass(frozen=True)
class LearningConfig:
    steps: int = 64
    seed: int = 72
    learning_rate: float = 0.2
    initial_prediction: float = 0.5

    def __post_init__(self):
        if not 1 <= self.steps <= 500 or not 0 <= self.seed <= 2**32 - 1:
            raise ValueError("steps or seed out of range")
        for v in (self.learning_rate, self.initial_prediction):
            if not isfinite(v) or not 0 <= v <= 1:
                raise ValueError("parameters must be finite in [0,1]")


def observations(config: LearningConfig) -> list[int]:
    state = config.seed
    result = []
    for _ in range(config.steps):
        state = (1664525 * state + 1013904223) & 0xffffffff
        result.append(int(state / 2**32 < 0.65))
    return result


def run_learning(config: LearningConfig, *, learn: bool = True) -> dict:
    prediction = config.initial_prediction
    trace = []
    for index, outcome in enumerate(observations(config), 1):
        before = prediction
        error = (before - outcome) ** 2
        if learn:
            prediction = min(1.0, max(0.0, before + config.learning_rate * (outcome - before)))
        trace.append({"step": index, "prediction": round(before, 8),
                      "outcome": outcome, "squared_error": round(error, 8),
                      "prediction_after": round(prediction, 8)})
    payload = json.dumps(trace, sort_keys=True, separators=(",", ":"))
    return {"experimental": True, "learn": learn, "steps": config.steps,
            "mean_squared_error": round(sum(x["squared_error"] for x in trace) / config.steps, 8),
            "final_prediction": round(prediction, 8),
            "trace_sha256": sha256(payload.encode()).hexdigest(),
            "trace": trace, "consciousness_measure": False}


def compare_learning(config: LearningConfig) -> dict:
    learner = run_learning(config, learn=True)
    baseline = run_learning(config, learn=False)
    return {"config": asdict(config), "learner": learner, "baseline": baseline,
            "error_delta": round(baseline["mean_squared_error"] - learner["mean_squared_error"], 8),
            "interpretation": "Synthetic prediction error only; not evidence of consciousness."}
