"""Functional cognition benchmarks; scores do not measure consciousness."""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Sequence


@dataclass(frozen=True)
class Prediction:
    confidence: float
    correct: bool

    def __post_init__(self) -> None:
        if not isfinite(self.confidence) or not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be finite and between 0 and 1")


def brier_score(predictions: Sequence[Prediction]) -> float:
    """Mean squared probability error; lower is better."""
    if not predictions:
        raise ValueError("At least one prediction required")
    return sum((p.confidence - float(p.correct)) ** 2 for p in predictions) / len(predictions)


def calibration_bins(predictions: Sequence[Prediction], bins: int = 10) -> list[dict]:
    if not 1 <= bins <= 100:
        raise ValueError("bins must be between 1 and 100")
    result = []
    for index in range(bins):
        group = [p for p in predictions if min(int(p.confidence * bins), bins - 1) == index]
        if group:
            result.append({
                "bin": index,
                "count": len(group),
                "mean_confidence": sum(p.confidence for p in group) / len(group),
                "accuracy": sum(p.correct for p in group) / len(group),
            })
    return result


def benchmark_report(predictions: Sequence[Prediction]) -> dict:
    return {
        "n": len(predictions),
        "brier_score": brier_score(predictions),
        "calibration_bins": calibration_bins(predictions),
        "interpretation": "Predictive calibration only; not evidence of subjective experience.",
    }
