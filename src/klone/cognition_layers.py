"""Layer-level activation probes for a small deterministic local neural network.

A toy network, NOT introspection into a hosted or proprietary LLM.
"""
from __future__ import annotations
from hashlib import sha256
from math import tanh, isfinite
import json


def probe_layers(inputs: list[float], *, seed: int = 72) -> dict:
    if not 1 <= len(inputs) <= 32 or not 0 <= seed <= 2**32 - 1:
        raise ValueError("input or seed bounds exceeded")
    if any(not isfinite(x) or abs(x) > 1 for x in inputs):
        raise ValueError("inputs must be finite in [-1,1]")
    state = seed
    layers = []
    current = inputs[:]
    for layer_id, width in enumerate((8, 8, 4), 1):
        weights = []
        for _ in range(width):
            row = []
            for _ in current:
                state = (1664525 * state + 1013904223) & 0xffffffff
                row.append(round((state / 2**32) * 2 - 1, 6))
            weights.append(row)
        current = [round(tanh(sum(w * x for w, x in zip(row, current)) /
                               max(1, len(current))), 6) for row in weights]
        layers.append({"layer": layer_id, "activations": current,
                       "weights_digest": sha256(json.dumps(weights).encode()).hexdigest()})
    trace_hash = sha256(json.dumps(layers, sort_keys=True).encode()).hexdigest()
    return {"experimental": True, "model": "toy_dense_network",
            "layers": layers, "trace_hash": trace_hash,
            "actual_llm_instrumented": False}
