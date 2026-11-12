"""NeuroCortex research simulator: six bounded modulators and vertical state slices.

Biological inspiration only. No subjective reward, hormone synthesis, tools or writes.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from hashlib import sha256
from math import isfinite
import json


NAMES = ("dopamine", "noradrenaline", "acetylcholine", "serotonin", "gaba", "glutamate")
MODULES = ("sensory", "attention", "workspace", "memory", "planning", "output")


def clamp(x: float) -> float:
    return round(max(0.0, min(1.0, x)), 6)


def digest(value: object) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                             allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class CortexConfig:
    steps: int = 64
    seed: int = 72
    learning_rate: float = 0.2
    modulation: bool = True
    snapshot_interval: int = 16

    def __post_init__(self) -> None:
        if not 1 <= self.steps <= 500 or not 1 <= self.snapshot_interval <= 500:
            raise ValueError("invalid experiment bounds")
        if not 0 <= self.seed <= 2**32 - 1:
            raise ValueError("invalid seed")
        if not isfinite(self.learning_rate) or not 0 <= self.learning_rate <= 1:
            raise ValueError("invalid learning rate")


def run_cortex(config: CortexConfig) -> dict:
    state = {name: 0.5 for name in NAMES}
    modules = {name: 0.5 for name in MODULES}
    prediction = 0.5
    rng = config.seed
    previous_hash = "0" * 64
    deltas = []
    snapshots = []
    errors = []
    for tick in range(1, config.steps + 1):
        rng = (1664525 * rng + 1013904223) & 0xffffffff
        observation = int(rng / 2**32 < 0.65)
        error = observation - prediction
        surprise = abs(error)
        errors.append(error * error)
        old = dict(state)
        if config.modulation:
            targets = {
                "dopamine": clamp(0.5 + error / 2),
                "noradrenaline": clamp(surprise),
                "acetylcholine": clamp(1 - surprise),
                "serotonin": clamp(1 - abs(error) / 2),
                "gaba": clamp(0.7 - surprise / 2),
                "glutamate": clamp(0.3 + surprise / 2),
            }
            state = {name: clamp(0.8 * old[name] + 0.2 * targets[name])
                     for name in NAMES}
        attention_gain = clamp(state["acetylcholine"] * state["noradrenaline"])
        inhibition = state["gaba"]
        excitation = state["glutamate"]
        modules = {
            "sensory": float(observation),
            "attention": attention_gain,
            "workspace": clamp(attention_gain * excitation),
            "memory": clamp(0.7 * modules["memory"] + 0.3 * observation),
            "planning": clamp(1 - surprise),
            "output": clamp((1 - inhibition) * excitation),
        }
        rate = config.learning_rate
        if config.modulation:
            rate *= (0.5 + state["dopamine"]) * (1 - 0.5 * inhibition)
        prediction = clamp(prediction + rate * error)
        vertical = {"step": tick, "observation": observation,
                    "prediction": prediction, "modules": modules,
                    "modulators": state}
        state_hash = digest({"previous": previous_hash, "state": vertical})
        deltas.append({"step": tick, "prediction_error": round(error, 6),
                       "modulator_delta": {name: round(state[name] - old[name], 6)
                                           for name in NAMES},
                       "previous_hash": previous_hash, "state_hash": state_hash})
        if tick == 1 or tick % config.snapshot_interval == 0 or tick == config.steps:
            snapshots.append({"step": tick, "vertical_slice": vertical,
                              "state_hash": state_hash})
        previous_hash = state_hash
    return {"experimental": True, "config": asdict(config),
            "mean_squared_error": round(sum(errors) / len(errors), 8),
            "trace_root": previous_hash, "deltas": deltas, "snapshots": snapshots,
            "no_external_actions": True, "subjective_experience_claim": False}


def compare_cortex(config: CortexConfig) -> dict:
    with_modulation = run_cortex(config)
    without_modulation = run_cortex(CortexConfig(
        steps=config.steps, seed=config.seed, learning_rate=config.learning_rate,
        modulation=False, snapshot_interval=config.snapshot_interval))
    return {"modulated": with_modulation, "unmodulated": without_modulation,
            "error_improvement": round(without_modulation["mean_squared_error"] -
                                       with_modulation["mean_squared_error"], 8),
            "note": "Synthetic analogues; neither result proves biological fidelity."}
