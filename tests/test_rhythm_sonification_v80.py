import io
import struct
import tempfile
import unittest
import wave
from pathlib import Path

from klone.rhythm_sonification import rhythm_wav, main, SAMPLE_RATE, TONE_FRAMES
from klone.mathematical_rhythm import rhythm_study


def decode(data):
    with wave.open(io.BytesIO(data), "rb") as source:
        params = source.getparams()
        raw = source.readframes(source.getnframes())
    return params, struct.unpack("<" + "h" * (len(raw) // 2), raw)


class RhythmSonificationV80(unittest.TestCase):
    def test_pcm_format(self):
        p, samples = decode(rhythm_wav(8, 3))
        self.assertEqual((p.nchannels, p.sampwidth, p.framerate), (1, 2, 16000))
        self.assertEqual(len(samples), 32000)

    def test_72_pattern_alignment(self):
        p, samples = decode(rhythm_wav(72, 8, cycles=1))
        self.assertEqual(p.nframes, 144000)
        pattern = rhythm_study(72, 8)["pattern"]
        for i, active in enumerate(pattern):
            chunk = samples[i * 2000:(i + 1) * 2000]
            self.assertEqual(any(chunk), bool(active))
            self.assertFalse(any(chunk[TONE_FRAMES:]))

    def test_silence(self):
        _, samples = decode(rhythm_wav(8, 0, cycles=1))
        self.assertFalse(any(samples))

    def test_bounded_amplitude_and_envelope(self):
        _, samples = decode(rhythm_wav(1, 1, cycles=1))
        self.assertLessEqual(max(map(abs, samples)), 6000)
        self.assertEqual(samples[0], 0)
        self.assertEqual(samples[TONE_FRAMES - 1], 0)
        self.assertGreater(max(map(abs, samples)), 1000)

    def test_noninteger_step_rounding(self):
        p, samples = decode(rhythm_wav(72, 72, bpm=137, cycles=4))
        self.assertEqual(p.nframes, (288 * SAMPLE_RATE * 15 + 137 // 2) // 137)
        self.assertEqual(len(samples), p.nframes)

    def test_reproducibility(self):
        self.assertEqual(rhythm_wav(16, 7), rhythm_wav(16, 7))

    def test_invalid_parameters(self):
        for kwargs in ({"bpm": 59}, {"bpm": 181}, {"bpm": True},
                       {"cycles": 0}, {"cycles": 5}, {"cycles": 1.0}):
            with self.assertRaises(ValueError):
                rhythm_wav(8, 3, **kwargs)

    def test_cli_exclusive_output(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rhythm.wav"
            args = ["--steps", "8", "--pulses", "3", "--output", str(path)]
            self.assertEqual(main(args), 0)
            original = path.read_bytes()
            self.assertEqual(original, rhythm_wav(8, 3))
            with self.assertRaises(SystemExit) as error:
                main(args)
            self.assertEqual(error.exception.code, 2)
            self.assertEqual(path.read_bytes(), original)
