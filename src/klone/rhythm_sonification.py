"""Original musical pulse sonification for bounded circular rhythms."""
from __future__ import annotations

import argparse
import io
import math
from pathlib import Path
import struct
import wave

from .mathematical_rhythm import rhythm_study

SAMPLE_RATE = 16000
TONE_FRAMES = 640


def rhythm_wav(steps: int, pulses: int, *, bpm: int = 120,
               cycles: int = 2) -> bytes:
    """Render a fixed soft 440 Hz pulse, four grid steps per beat."""
    pattern = rhythm_study(steps, pulses)["pattern"]
    if type(bpm) is not int or not 60 <= bpm <= 180:
        raise ValueError("Expected tempo from 60 to 180 BPM")
    if type(cycles) is not int or not 1 <= cycles <= 4:
        raise ValueError("Expected 1 to 4 cycles")
    total_steps = steps * cycles
    # Round absolute boundaries rather than accumulating rounding errors.
    boundaries = [(i * SAMPLE_RATE * 15 + bpm // 2) // bpm
                  for i in range(total_steps + 1)]
    tone = struct.pack("<" + "h" * TONE_FRAMES, *[
        round(6000 * math.sin(2 * math.pi * 440 * i / SAMPLE_RATE)
              * math.sin(math.pi * i / (TONE_FRAMES - 1)) ** 2)
        for i in range(TONE_FRAMES)
    ])
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setparams((1, 2, SAMPLE_RATE, 0, "NONE", "not compressed"))
        for i in range(total_steps):
            frames = boundaries[i + 1] - boundaries[i]
            if pattern[i % steps]:
                output.writeframesraw(tone + bytes(2 * (frames - TONE_FRAMES)))
            else:
                output.writeframesraw(bytes(2 * frames))
    return buffer.getvalue()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--steps", type=int, default=72)
    parser.add_argument("--pulses", type=int, default=8)
    parser.add_argument("--bpm", type=int, default=120)
    parser.add_argument("--cycles", type=int, default=2)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        data = rhythm_wav(args.steps, args.pulses, bpm=args.bpm, cycles=args.cycles)
        # Exclusive creation: never overwrite an existing creative file.
        with args.output.open("xb") as output:
            output.write(data)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
