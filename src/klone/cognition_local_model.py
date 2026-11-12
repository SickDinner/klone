"""Optional local PyTorch activation instrumentation for KLONE.

Explicitly opt-in; works only on models already loaded in this Python process.
No model downloads, external services, gradients, or persistent raw activations.
"""
from __future__ import annotations
from hashlib import sha256
from math import isfinite
import json


def summarize_tensor(tensor, *, max_values: int = 16) -> dict:
    """Detach and summarize a tensor without retaining its computational graph."""
    if not 1 <= max_values <= 64:
        raise ValueError("max_values must be 1..64")
    if isinstance(tensor, (tuple, list)):
        tensor = next((item for item in tensor if hasattr(item, "detach")), None)
    if tensor is None or not hasattr(tensor, "detach"):
        return {"kind": "non_tensor"}
    detached = tensor.detach()
    if hasattr(detached, "is_sparse") and detached.is_sparse:
        return {"kind": "unsupported_sparse"}
    flat = detached.reshape(-1)
    count = int(flat.numel())
    # Bound transfer to host memory: sampled values only.
    if count:
        indexes = [min(count - 1, (i * count) // min(count, max_values))
                   for i in range(min(count, max_values))]
        values = [float(flat[i].item()) for i in indexes]
    else:
        values = []
    finite_values = [v for v in values if isfinite(v)]
    return {
        "kind": "tensor",
        "shape": list(detached.shape),
        "elements": count,
        "sampled": len(values),
        "nonfinite_sampled": len(values) - len(finite_values),
        "sample_mean": round(sum(finite_values) / len(finite_values), 8)
                       if finite_values else None,
        "sample_abs_max": round(max(map(abs, finite_values)), 8)
                          if finite_values else None,
    }


def inspect_local_model(model, forward, *, max_layers: int = 12,
                        max_values: int = 16) -> dict:
    """Run a caller-provided local inference function with temporary forward hooks.

    The caller is responsible for trusted model/input setup and inference mode.
    Hooks are removed even when forward raises. Never logs token IDs or prompts.
    """
    if not 1 <= max_layers <= 64:
        raise ValueError("max_layers must be 1..64")
    if not callable(forward) or not hasattr(model, "named_modules"):
        raise ValueError("local model and callable forward required")
    records = []
    handles = []
    modules = [(name, module) for name, module in model.named_modules()
               if name and hasattr(module, "register_forward_hook")]
    # Choose leaf modules to avoid redundant container activations.
    leaves = [(name, module) for name, module in modules
              if not any(other.startswith(name + ".") for other, _ in modules)]
    try:
        for name, module in leaves[:max_layers]:
            def hook(_module, _inputs, output, layer_name=name):
                if len(records) < max_layers:
                    records.append({"layer": layer_name,
                                    "summary": summarize_tensor(output, max_values=max_values)})
            handles.append(module.register_forward_hook(hook))
        forward()
    finally:
        for handle in handles:
            handle.remove()
    encoded = json.dumps(records, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return {"experimental": True, "actual_local_model_instrumented": True,
            "layer_count": len(records), "layers": records,
            "trace_sha256": sha256(encoded.encode()).hexdigest(),
            "raw_activations_saved": False, "prompts_saved": False}
