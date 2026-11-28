"""Original creative sonification of a fixed synthetic RGB palette.

A deliberately chosen artistic mapping, not a physical color-sound equivalence.
"""
from __future__ import annotations

import argparse
import io
import json
import math
from pathlib import Path
import struct
import wave

SAMPLE_RATE = 16000
NOTE_FRAMES = 4000
SCALE = (0, 2, 4, 7, 9)
PALETTES = {
    "dusk": ((1, 2, 3), (7, 2, 1), (6, 5, 2)),
    "winter": ((1, 2, 5), (4, 6, 7), (7, 7, 7)),
}


def palette_score(name: str = "dusk") -> dict:
    if not isinstance(name, str) or name not in PALETTES:
        raise ValueError("Expected dusk or winter synthetic palette")
    notes = []
    for red, green, blue in PALETTES[name]:
        degree = (red + 2 * green + 3 * blue) % len(SCALE)
        midi = 60 + SCALE[degree] + (12 if max(red, green, blue) >= 6 else 0)
        notes.append({
            "rgb_bin": [red, green, blue],
            "midi_note": midi,
            "frequency_hz": round(440 * 2 ** ((midi - 69) / 12), 8),
            "duration_frames": NOTE_FRAMES,
        })
    return {
        "schema": "klone.synthetic_palette_melody.v1",
        "palette": name,
        "sample_rate_hz": SAMPLE_RATE,
        "notes": notes,
        "limitations": [
            "Fixed synthetic palette; no image input or recognition.",
            "Arbitrary pentatonic artistic mapping, not physical or neurological equivalence.",
            "Original short melody; no aesthetic or emotional inference.",
        ],
    }


def palette_wav(name: str = "dusk") -> bytes:
    score = palette_score(name)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setparams((1, 2, SAMPLE_RATE, 0, "NONE", "not compressed"))
        for note in score["notes"]:
            frequency = note["frequency_hz"]
            values = [
                round(5000 * math.sin(2 * math.pi * frequency * i / SAMPLE_RATE)
                      * math.sin(math.pi * i / (NOTE_FRAMES - 1)) ** 2)
                for i in range(NOTE_FRAMES)
            ]
            output.writeframesraw(struct.pack("<" + "h" * len(values), *values))
    return buffer.getvalue()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--palette", choices=tuple(PALETTES), default="dusk")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        score = palette_score(args.palette)
        if args.output is not None:
            with args.output.open("xb") as output:
                output.write(palette_wav(args.palette))
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(score, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
