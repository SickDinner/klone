"""Spatial composition of fixed synthetic binary art patterns.

Coordinates are cell indices. Metrics describe structure, not beauty,
human gaze, scene understanding or perceptual validation.
"""
from __future__ import annotations

import argparse
import json
import math

PATTERNS = (
    ("centered_square", ("00000000", "00000000", "00111100", "00111100",
                         "00111100", "00111100", "00000000", "00000000")),
    ("offset_square", ("11110000", "11110000", "11110000", "11110000",
                       "00000000", "00000000", "00000000", "00000000")),
    ("vertical_bands", ("01000100",)*8),
    ("checker_sparse", ("10101010", "00000000")*4),
    ("diagonal", ("10000000", "01000000", "00100000", "00010000",
                  "00001000", "00000100", "00000010", "00000001")),
    ("empty", ("00000000",)*8),
    ("full", ("11111111",)*8),
)


def composition(rows):
    """Describe a rectangular binary raster, foreground=1, background=0."""
    if not rows or not rows[0]:
        raise ValueError("nonempty rectangular binary raster required")
    w, h = len(rows[0]), len(rows)
    if any(len(row) != w or any(c not in "01" for c in row) for row in rows):
        raise ValueError("nonempty rectangular binary raster required")
    n = w*h
    points = [(x, y) for y, row in enumerate(rows)
              for x, c in enumerate(row) if c == "1"]
    count = len(points)
    center = ((w-1)/2, (h-1)/2)
    centroid = None
    offset = None
    bbox = None
    if count:
        cx = sum(x for x, y in points)/count
        cy = sum(y for x, y in points)/count
        centroid = [cx, cy]
        half_diagonal = math.hypot(*center)
        offset = math.dist(centroid, center)/half_diagonal if half_diagonal else 0.0
        bbox = [min(x for x, y in points), min(y for x, y in points),
                max(x for x, y in points)+1, max(y for x, y in points)+1]
    def agreement(transform):
        return sum(rows[y][x] == rows[ty][tx]
                   for y in range(h) for x in range(w)
                   for tx, ty in (transform(x, y),))/n
    # Internal grid edges only: no implicit exterior background.
    pairs = h*(w-1) + w*(h-1)
    changes = sum(rows[y][x] != rows[y][x+1]
                  for y in range(h) for x in range(w-1))
    changes += sum(rows[y][x] != rows[y+1][x]
                   for y in range(h-1) for x in range(w))
    remaining = set(points)
    components = []
    while remaining:
        stack = [remaining.pop()]
        size = 0
        while stack:
            x, y = stack.pop()
            size += 1
            for p in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                if p in remaining:
                    remaining.remove(p)
                    stack.append(p)
        components.append(size)
    return {
        "width": w, "height": h, "foreground_cells": count,
        "foreground_fraction": count/n, "negative_space_fraction": (n-count)/n,
        "foreground_centroid_xy": centroid,
        "normalized_centroid_offset": offset,
        "foreground_bbox_xyxy_exclusive": bbox,
        "left_right_agreement": agreement(lambda x,y:(w-1-x,y)),
        "top_bottom_agreement": agreement(lambda x,y:(x,h-1-y)),
        "rotation_180_agreement": agreement(lambda x,y:(w-1-x,h-1-y)),
        "internal_neighbor_edges": pairs,
        "internal_transition_edges": changes,
        "internal_transition_fraction": changes/pairs if pairs else None,
        "foreground_component_count_4": len(components),
        "foreground_component_sizes_4": sorted(components, reverse=True),
    }


def spatial_study():
    return {
        "schema": "klone.spatial_composition_study.v1",
        "observations": [{"example": name, "raster": list(rows),
                          "metrics": composition(rows)} for name, rows in PATTERNS],
        "limitations": [
            "Seven fixed synthetic binary art patterns; no external image input.",
            "Equal cell weights; no color, texture, gaze or observer measurement.",
            "Agreement includes background; empty and full patterns are symmetric.",
            "Centroid offset is not artistic balance; transitions are not general complexity.",
            "Four-neighbor connectivity; bounding boxes use exclusive upper bounds.",
            "No production integration, aesthetic quality or consciousness claim.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    print(json.dumps(spatial_study(), indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
