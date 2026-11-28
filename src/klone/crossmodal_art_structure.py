"""Explicit cross-domain structural analogies in fixed synthetic art fixtures.

Compare only declared mathematical descriptors; no learned associations,
semantic inference, observer claims, or aggregate similarity scores.
"""
from __future__ import annotations

import argparse
import json
import math

from .spatial_composition_study import PATTERNS as SPATIAL, composition
from .temporal_rhythm_study import PATTERNS as RHYTHMS, rhythm_metrics
from .musical_spectrum_study import FIXTURES as SPECTRA, spectrum_metrics


def _binary_entropy(p):
    return -sum(x*math.log2(x) for x in (p,1-p) if x)


def _profile(domain, name, features):
    return {"domain": domain, "example": name, "features": features}


def profiles():
    result = []
    for name, rows in SPATIAL:
        m = composition(rows)
        p = m["foreground_fraction"]
        result.append(_profile("spatial", name, {
            "binary_occupancy_fraction": p,
            "binary_occupancy_entropy_bits": _binary_entropy(p),
            "local_transition_fraction": m["internal_transition_fraction"],
        }))
    for name, pattern in RHYTHMS:
        m = rhythm_metrics(pattern)
        result.append(_profile("rhythm", name, {
            "binary_occupancy_fraction": m["onset_density"],
            "binary_occupancy_entropy_bits": m["binary_entropy_bits"],
            "local_transition_fraction": m["cyclic_transition_fraction"],
        }))
    for name, fundamental, amplitudes in SPECTRA:
        m = spectrum_metrics(fundamental, amplitudes)
        # Presence of a harmonic slot is a different encoding from power.
        p = m["active_harmonic_count"]/len(amplitudes)
        result.append(_profile("spectrum", name, {
            "binary_occupancy_fraction": p,
            "binary_occupancy_entropy_bits": _binary_entropy(p),
            "local_transition_fraction": None,
        }))
    return result


def compare(first, second):
    """Report descriptor-wise absolute differences, with missingness explicit."""
    keys = ("binary_occupancy_fraction", "binary_occupancy_entropy_bits",
            "local_transition_fraction")
    deltas = {}
    for key in keys:
        a,b = first["features"].get(key), second["features"].get(key)
        deltas[key] = None if a is None or b is None else abs(a-b)
    return {
        "first": [first["domain"], first["example"]],
        "second": [second["domain"], second["example"]],
        "absolute_descriptor_differences": deltas,
        "exact_descriptor_matches": [key for key in keys if deltas[key] == 0],
        "undefined_descriptors": [key for key in keys if deltas[key] is None],
    }


def crossmodal_study():
    rows = profiles()
    pairs = [compare(a,b) for i,a in enumerate(rows) for b in rows[i+1:]
             if a["domain"] != b["domain"]]
    return {
        "schema": "klone.crossmodal_art_structure.v1",
        "descriptor_definitions": {
            "binary_occupancy_fraction": "Foreground cells, onset slots, or nonzero harmonic slots divided by all declared slots.",
            "binary_occupancy_entropy_bits": "Bernoulli entropy of that binary encoding; not spectral power entropy.",
            "local_transition_fraction": "Spatial internal four-neighbor edges or cyclic temporal neighbor edges; undefined for spectrum.",
        },
        "profiles": rows,
        "cross_domain_comparisons": pairs,
        "limitations": [
            "Fixed synthetic art fixtures inherited from V10.6 through V10.8.",
            "Occupancy depends on chosen grid and harmonic slot count.",
            "Equal occupancy entails equal binary entropy; these are not independent evidence.",
            "Spatial and temporal adjacency use different boundary conventions.",
            "Missing descriptors are null, never zero or imputed.",
            "Exact descriptor matches are mathematical analogies, not evidence of perceptual, semantic or aesthetic equivalence.",
            "No learned mapping, composite score, real media input, memory write or production integration.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    print(json.dumps(crossmodal_study(), indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
