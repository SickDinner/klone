"""Reproducible multi-seed comparison for bounded predictive learning."""
from __future__ import annotations

from statistics import mean, stdev
from .cognition_learning import LearningConfig, compare_learning


def sweep(*, seeds: tuple[int, ...] = (11, 29, 47, 72, 101),
          rates: tuple[float, ...] = (0.0, 0.05, 0.1, 0.2, 0.4),
          steps: int = 64) -> dict:
    if not 1 <= len(seeds) <= 32 or not 1 <= len(rates) <= 16:
        raise ValueError("sweep size out of bounds")
    if len(set(seeds)) != len(seeds):
        raise ValueError("seeds must be distinct")
    records = []
    for rate in rates:
        deltas = []
        for seed in seeds:
            report = compare_learning(LearningConfig(
                steps=steps, seed=seed, learning_rate=rate))
            deltas.append(report["error_delta"])
        records.append({
            "learning_rate": rate,
            "mean_improvement": round(mean(deltas), 8),
            "sample_std": round(stdev(deltas), 8) if len(deltas) > 1 else None,
            "seeds": len(seeds),
            "individual_deltas": deltas,
        })
    best = sorted(records, key=lambda r: (-r["mean_improvement"], r["learning_rate"]))[0]
    return {
        "experimental": True,
        "best_rate_in_sample": best["learning_rate"],
        "results": records,
        "warning": "Exploratory in-sample selection; use independent held-out seeds for validation.",
    }
