"""Educational spatial information study of fixed binary abstract artworks."""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math

SIZE = 32
PATTERNS = ("vertical_split", "horizontal_split", "checkerboard", "vertical_stripes", "constant")


def _entropy(counts):
    total = sum(counts)
    return -math.fsum((c / total) * math.log2(c / total) for c in counts if c)


def _grid(name):
    return [[int(x >= SIZE // 2) if name == "vertical_split"
             else int(y >= SIZE // 2) if name == "horizontal_split"
             else (x + y) % 2 if name == "checkerboard"
             else x % 2 if name == "vertical_stripes"
             else 0 for x in range(SIZE)] for y in range(SIZE)]


def _pair_statistics(pairs):
    joint = Counter(pairs)
    first, second = Counter(), Counter()
    for (a, b), count in joint.items():
        first[a] += count
        second[b] += count
    ha = _entropy(first.values())
    hb = _entropy(second.values())
    hab = _entropy(joint.values())
    return {
        "pair_count": sum(joint.values()),
        "joint_counts": {f"{a}{b}": joint[a, b] for a in range(2) for b in range(2)},
        "first_entropy_bits": ha,
        "second_entropy_bits": hb,
        "joint_entropy_bits": hab,
        "conditional_second_given_first_bits": max(0.0, hab - ha),
        "mutual_information_bits": max(0.0, ha + hb - hab),
    }


def spatial_information_study():
    """Measure neighbor statistics on five fixed synthetic grids."""
    observations = []
    for name in PATTERNS:
        grid = _grid(name)
        marginal = Counter(v for row in grid for v in row)
        observations.append({
            "pattern": name,
            "pixel_entropy_bits": _entropy(marginal.values()),
            "horizontal": _pair_statistics(
                (grid[y][x], grid[y][x + 1])
                for y in range(SIZE) for x in range(SIZE - 1)),
            "vertical": _pair_statistics(
                (grid[y][x], grid[y + 1][x])
                for y in range(SIZE - 1) for x in range(SIZE)),
        })
    return {
        "schema": "klone.spatial_information.v1",
        "dimensions": [SIZE, SIZE],
        "observations": observations,
        "limitations": [
            "Fixed binary mathematical artwork only; no external image input.",
            "Ordered adjacent pairs, excluding wraparound; empirical frequency estimates.",
            "Mutual information measures statistical dependence, not visual complexity.",
            "No estimator bias correction or inference about artistic quality.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    print(json.dumps(spatial_information_study(), indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
