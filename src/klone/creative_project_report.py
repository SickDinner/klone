"""Explicit local creative project reports and conservative palette comparison."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import wave

from .artwork_color_metrics import artwork_color_metrics
from .music_clip_spectrum import music_clip_spectrum
from .written_verse_rhythm import written_verse_rhythm
from .lyrics_metrics import MAX_BYTES
from .creative_dashboard import render_creative_dashboard


def compare_palettes(before: dict, after: dict) -> dict:
    """Total variation of complete sampled encoded RGB histograms only."""
    if any(r["schema"] != "klone.artwork_color_metrics.v1" for r in (before, after)):
        raise ValueError("Unsupported palette schema")
    if any(r["occupied_rgb_bins"] != len(r["dominant_bins"]) for r in (before, after)):
        return {"total_variation": None, "status": "incomplete_histogram"}
    a, b = ({tuple(item["rgb_bin"]): item["fraction"]
             for item in r["dominant_bins"]} for r in (before, after))
    distance = sum(abs(a.get(key, 0) - b.get(key, 0)) for key in a.keys() | b.keys()) / 2
    return {
        "total_variation": round(min(1.0, distance), 8),
        "status": "descriptive_only",
        "limitations": ["Rounded sampled RGB distributions, not perceptual color difference.",
                        "Spatial composition and image identity are not compared."],
    }


def creative_project_report(artwork: Path, music_clip: Path, lyrics: Path) -> dict:
    with lyrics.open("rb") as source:
        raw = source.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Lyrics exceed byte limit")
    return {
        "schema": "klone.creative_project_report.v1",
        "artwork": artwork_color_metrics(artwork),
        "music_clip": music_clip_spectrum(music_clip),
        "verse": written_verse_rhythm(raw.decode("utf-8")),
        "limitations": ["Independent descriptive measurements of explicitly supplied creative files.",
                        "No cross-modal semantic correspondence or quality claim."],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artwork", type=Path, required=True)
    parser.add_argument("--music-clip", type=Path, required=True)
    parser.add_argument("--lyrics", type=Path, required=True)
    parser.add_argument("--format", choices=("json", "html"), default="json")
    args = parser.parse_args(argv)
    try:
        report = creative_project_report(args.artwork, args.music_clip, args.lyrics)
    except (ValueError, OSError, EOFError, wave.Error) as exc:
        parser.error(str(exc))
    if args.format == "html":
        print(render_creative_dashboard(report))
    else:
        print(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
