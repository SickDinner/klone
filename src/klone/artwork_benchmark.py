"""Repeatable timing and Python-allocation measurements on synthetic artwork.

Fixture creation is excluded from measurements. No arbitrary benchmark callbacks.
"""
from __future__ import annotations

import argparse
import json
import platform
import statistics
import tempfile
import time
import tracemalloc
from pathlib import Path

import PIL
from PIL import Image

from .artwork_color_metrics import artwork_color_metrics


def benchmark_artwork(repetitions: int = 5) -> dict:
    if type(repetitions) is not int or not 2 <= repetitions <= 10:
        raise ValueError("Expected 2 to 10 repetitions")
    if tracemalloc.is_tracing():
        raise ValueError("Run benchmark without an existing allocation trace")
    with tempfile.TemporaryDirectory(prefix="klone-art-benchmark-") as directory:
        path = Path(directory) / "synthetic.png"
        image = Image.new("RGB", (256, 256), (32, 64, 96))
        image.paste((224, 192, 160), (128, 0, 256, 256))
        image.save(path)
        image.close()
        reference = artwork_color_metrics(path)
        durations = []
        for _ in range(repetitions):
            start = time.perf_counter_ns()
            observed = artwork_color_metrics(path)
            durations.append(time.perf_counter_ns() - start)
            if observed != reference:
                raise RuntimeError("Fixture result changed between repetitions")
        peaks = []
        for _ in range(repetitions):
            tracemalloc.start()
            try:
                observed = artwork_color_metrics(path)
                _, peak = tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop()
            if observed != reference:
                raise RuntimeError("Fixture result changed during allocation measurement")
            peaks.append(peak)
    return {
        "schema": "klone.artwork_benchmark.v1",
        "fixture": "synthetic_two_color_256x256_png",
        "repetitions_per_measurement": repetitions,
        "environment": {
            "system": platform.system(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "pillow": PIL.__version__,
        },
        "wall_time_ns": {"samples": durations, "median": statistics.median(durations),
                         "minimum": min(durations), "maximum": max(durations)},
        "python_traced_peak_bytes": {"samples": peaks, "median": statistics.median(peaks),
                                     "maximum": max(peaks)},
        "fixture_results_equal": True,
        "limitations": [
            "One warm-up; separate timing and traced-allocation runs; temporary synthetic fixture.",
            "Tracemalloc measures traced Python allocations, not total process RSS or all native allocations.",
            "No CPU load or thermal control; not a cross-device performance ranking.",
            "No inference about whole-application performance.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repetitions", type=int, default=5)
    args = parser.parse_args(argv)
    try:
        report = benchmark_artwork(args.repetitions)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
