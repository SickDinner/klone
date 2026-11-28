"""Original audiovisual miniature from a fixed mathematical score.

The color/pitch mapping is an artistic convention, not sensory equivalence.
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
NOTES = (60, 64, 67, 72, 69, 67, 64, 60)
COLORS = ("#305070", "#82e5d8", "#eab856", "#e2e8f0")


def synesthetic_score():
    events = []
    for i, midi in enumerate(NOTES):
        events.append({
            "index": i,
            "midi_note": midi,
            "frequency_hz": round(440 * 2 ** ((midi - 69) / 12), 8),
            "start_frame": i * NOTE_FRAMES,
            "duration_frames": NOTE_FRAMES,
            "angle_degrees": i * 45,
            "radius": 48 + 4 * (midi - 60),
            "color": COLORS[i % len(COLORS)],
        })
    return {
        "schema": "klone.synesthetic_art.v1",
        "sample_rate_hz": SAMPLE_RATE,
        "duration_frames": len(events) * NOTE_FRAMES,
        "events": events,
        "limitations": [
            "Fixed original synthetic composition, no external input.",
            "Pitch controls radius by a chosen artistic rule; color follows event index.",
            "No physical or neurological equivalence between sound and color.",
            "No perceptual or aesthetic quality claim.",
        ],
    }


def render_synesthetic_svg():
    elements = []
    for event in synesthetic_score()["events"]:
        a = math.radians(event["angle_degrees"] - 90)
        x = 150 + event["radius"] * math.cos(a)
        y = 150 + event["radius"] * math.sin(a)
        color = event["color"]
        elements.append(
            f'<line x1="150" y1="150" x2="{x:.6f}" y2="{y:.6f}" stroke="{color}"/>'
            f'<circle cx="{x:.6f}" cy="{y:.6f}" r="9" fill="{color}"/>'
        )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 300" role="img">'
        '<title>Original eight-note geometric miniature</title>'
        '<rect width="300" height="300" fill="#152336"/>'
        '<circle cx="150" cy="150" r="96" fill="none" stroke="#64748b"/>'
        + "".join(elements) + '</svg>'
    )


def synesthetic_wav():
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setparams((1, 2, SAMPLE_RATE, 0, "NONE", "not compressed"))
        for event in synesthetic_score()["events"]:
            frequency = event["frequency_hz"]
            samples = [
                round(5000 * math.sin(2 * math.pi * frequency * i / SAMPLE_RATE)
                      * math.sin(math.pi * i / (NOTE_FRAMES - 1)) ** 2)
                for i in range(NOTE_FRAMES)
            ]
            output.writeframesraw(struct.pack("<" + "h" * len(samples), *samples))
    return buffer.getvalue()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("json", "svg"), default="json")
    parser.add_argument("--audio-output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.audio_output is not None:
            with args.audio_output.open("xb") as handle:
                handle.write(synesthetic_wav())
    except OSError as exc:
        parser.error(str(exc))
    print(render_synesthetic_svg() if args.format == "svg"
          else json.dumps(synesthetic_score(), indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
