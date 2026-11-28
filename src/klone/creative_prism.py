"""Local creative research perspectives with no combined quality score."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import wave

from .artwork_color_metrics import artwork_color_metrics
from .lyrics_metrics import analyze_lyrics, MAX_BYTES
from .written_verse_rhythm import written_verse_rhythm
from .music_pcm_metrics import analyze_music_wav
from .music_clip_spectrum import music_clip_spectrum


def creative_prism(artwork: Path, music: Path, lyrics: Path) -> dict:
    with lyrics.open("rb") as source:
        raw = source.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Lyrics exceed byte limit")
    text = raw.decode("utf-8")
    return {
        "schema": "klone.creative_prism.v1",
        "perspectives": {
            "visual_palette": artwork_color_metrics(artwork, full_histogram=True),
            "lexical_structure": analyze_lyrics(text),
            "written_rhythm": written_verse_rhythm(text),
            "audio_dynamics": analyze_music_wav(music),
            "leading_clip_spectrum": music_clip_spectrum(music),
        },
        "limitations": [
            "Separate descriptive perspectives on explicitly selected creative files.",
            "No combined quality score, semantic correspondence or author inference.",
            "Spectrum describes the leading clip, not the entire track.",
            "Lyrics and audio alignment is not verified.",
            "The measurements are not independent samples of a common latent trait.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artwork", type=Path, required=True)
    parser.add_argument("--music", type=Path, required=True)
    parser.add_argument("--lyrics", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = creative_prism(args.artwork, args.music, args.lyrics)
    except (OSError, ValueError, EOFError, wave.Error) as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
