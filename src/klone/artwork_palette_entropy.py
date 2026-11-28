"""Information-theoretic statistics of explicitly selected abstract artwork palettes."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from .artwork_color_metrics import artwork_color_metrics
from .artwork_palette_study import _distribution, compare_full_histograms


def _entropy(distribution):
    return math.fsum(-float(p) * math.log2(float(p))
                     for p in distribution.values() if p)


def palette_entropy(histogram):
    distribution = _distribution(histogram)
    entropy = _entropy(distribution)
    return {
        "occupied_bins": len(distribution),
        "entropy_bits": round(entropy, 8),
        "effective_color_bins": round(2 ** entropy, 8),
        "entropy_fraction_of_512_bin_maximum": round(entropy / 9, 8),
    }


def compare_palette_entropy(before, after):
    a, b = _distribution(before), _distribution(after)
    mixture = {k: (a.get(k, 0) + b.get(k, 0)) / 2
               for k in sorted(a.keys() | b.keys())}
    divergence = _entropy(mixture) - (_entropy(a) + _entropy(b)) / 2
    # The exact mathematical range is [0, 1]; clamp floating-point noise.
    divergence = min(1.0, max(0.0, divergence))
    return {
        "schema": "klone.palette_entropy_study.v1",
        "before": palette_entropy(before),
        "after": palette_entropy(after),
        "jensen_shannon_divergence_bits": round(divergence, 8),
        "jensen_shannon_distance": round(math.sqrt(divergence), 8),
        "total_variation": compare_full_histograms(before, after)["total_variation"],
        "limitations": [
            "Descriptive entropy of sampled encoded RGB bins, not spatial texture.",
            "Effective bins are a diversity index, not a count of unique original colors.",
            "Jensen-Shannon divergence uses equal weighting of the two distributions.",
            "No perceptual similarity, artistic quality or semantic inference.",
        ],
    }


def artwork_entropy_study(before: Path, after: Path):
    a = artwork_color_metrics(before, full_histogram=True)
    b = artwork_color_metrics(after, full_histogram=True)
    return compare_palette_entropy(a["full_histogram"], b["full_histogram"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    args = parser.parse_args(argv)
    try:
        result = artwork_entropy_study(args.before, args.after)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
