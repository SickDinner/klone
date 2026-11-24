"""Read-only group-aware predictive validation for Cognition/Council72 (LAB).

Declared source/evidence group IDs are NOT authenticated independence proofs.
Equal weighting by declared group reduces obvious duplicate-source inflation,
but cannot establish independence of two differently named groups.
No model training, inference, memory writes, or deployment authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from collections import defaultdict
import re
from collections.abc import Sequence

_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z')
_MAX_ITEMS = 20000
_MAX_GROUPS = 1024


def _valid_id(value: str) -> bool:
    return type(value) is str and bool(_ID.fullmatch(value))


@dataclass(frozen=True)
class GroupedPrediction:
    """One held-out prediction with a claimed common evidence lineage."""
    item_id: str
    declared_source_group: str
    confidence: float
    correct: bool

    def __post_init__(self) -> None:
        if not _valid_id(self.item_id) or not _valid_id(self.declared_source_group):
            raise ValueError('invalid_prediction_identifiers')
        if (type(self.confidence) not in (float, int) or
                not isfinite(self.confidence) or not 0 <= self.confidence <= 1):
            raise ValueError('invalid_prediction_confidence')
        if type(self.correct) is not bool:
            raise ValueError('truth_label_must_be_bool')


def evaluate_grouped_predictions(
    predictions: Sequence[GroupedPrediction], *,
    training_source_groups: frozenset[str],
    minimum_declared_groups: int = 5,
    calibration_bins: int = 10,
) -> dict:
    """Evaluate held-out predictions without counting repeated groups as new groups.

    Both the input scores and source-group labels are caller-provided claims.
    They do NOT prove test outcomes, independence, calibration in production,
    or readiness for autonomous actions.
    """
    if (not isinstance(predictions, Sequence) or isinstance(predictions, (str, bytes))
            or not 1 <= len(predictions) <= _MAX_ITEMS):
        raise ValueError('invalid_prediction_collection')
    if (type(training_source_groups) is not frozenset
            or any(not _valid_id(group) for group in training_source_groups)
            or len(training_source_groups) > _MAX_GROUPS):
        raise ValueError('invalid_training_groups')
    if (type(minimum_declared_groups) is not int
            or not 1 <= minimum_declared_groups <= _MAX_GROUPS):
        raise ValueError('invalid_minimum_declared_groups')
    if type(calibration_bins) is not int or not 2 <= calibration_bins <= 100:
        raise ValueError('invalid_calibration_bins')

    by_group = defaultdict(list)
    seen_items = set()
    for row in predictions:
        if not isinstance(row, GroupedPrediction):
            raise ValueError('invalid_prediction')
        if row.item_id in seen_items:
            raise ValueError('duplicate_prediction_item')
        seen_items.add(row.item_id)
        if row.declared_source_group in training_source_groups:
            raise ValueError('training_evaluation_lineage_overlap')
        by_group[row.declared_source_group].append(row)
    if len(by_group) > _MAX_GROUPS:
        raise ValueError('too_many_declared_groups')

    n = len(predictions)
    g = len(by_group)
    groups = []
    bucket_weight = [0.0] * calibration_bins
    bucket_prob = [0.0] * calibration_bins
    bucket_outcome = [0.0] * calibration_bins
    all_error = 0.0
    grouped_error = 0.0
    for group in sorted(by_group):
        rows = by_group[group]
        group_error = sum((float(row.confidence)-float(row.correct))**2 for row in rows)/len(rows)
        grouped_error += group_error/g
        all_error += group_error*len(rows)/n
        groups.append({
            'declared_source_group': group,
            'count': len(rows),
            'brier_score': round(group_error, 8),
        })
        # Every *claimed* group contributes total mass 1/g regardless of its size.
        for row in rows:
            bucket = min(int(float(row.confidence)*calibration_bins),calibration_bins-1)
            weight = 1/(g*len(rows))
            bucket_weight[bucket] += weight
            bucket_prob[bucket] += weight*float(row.confidence)
            bucket_outcome[bucket] += weight*float(row.correct)
    ece = sum(abs(bucket_prob[k]-bucket_outcome[k]) for k in range(calibration_bins))
    return {
        'schema_version': 1,
        'kind': 'klone-cognition-grouped-validation-v25-lab',
        'prediction_count': n,
        'declared_source_group_count': g,
        'minimum_declared_groups': minimum_declared_groups,
        'naive_brier': round(all_error, 8),
        'source_group_balanced_brier': round(grouped_error, 8),
        'source_group_balanced_ece': round(ece, 8),
        'largest_declared_group_fraction': round(max(len(v) for v in by_group.values())/n, 8),
        'groups': groups,
        'assessment': ('insufficient_declared_groups' if g < minimum_declared_groups
                       else 'manual_review_required'),
        'training_evaluation_overlap_detected': False,
        'origin_authenticated': False,
        'independent_sources_verified': False,
        'labels_grounded_in_external_evidence': False,
        'deployment_approval': False,
        'autonomous_decisions_allowed': False,
        'note': 'Group IDs are untrusted claims; repeated agent votes are not independent evidence.',
    }
