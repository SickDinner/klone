import struct
import tempfile
import unittest
import wave
from pathlib import Path

from klone.music_pcm_metrics import analyze_music_wav


class MusicPcmMetricsV53(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "fixture.wav"

    def write(self, samples, channels=1, rate=8000, width=2):
        with wave.open(str(self.path), "wb") as out:
            out.setparams((channels, width, rate, 0, "NONE", "not compressed"))
            raw = struct.pack("<" + "h" * len(samples), *samples) if width == 2 else bytes(samples)
            out.writeframes(raw)

    def test_silence(self):
        self.write([0] * 800)
        r = analyze_music_wav(self.path)
        self.assertEqual(r["duration_seconds"], 0.1)
        self.assertEqual(r["channels"][0]["rms"], 0)
        self.assertEqual(r["channels"][0]["zero_fraction"], 1)

    def test_known_amplitude(self):
        self.write([16384, -16384] * 20)
        r = analyze_music_wav(self.path)["channels"][0]
        self.assertEqual(r["peak"], 0.5)
        self.assertEqual(r["rms"], 0.5)
        self.assertEqual(r["mean"], 0)

    def test_stereo_separation(self):
        self.write([0, 16384] * 50, channels=2)
        r = analyze_music_wav(self.path)
        self.assertEqual(r["frames"], 50)
        self.assertEqual(r["channels"][0]["peak"], 0)
        self.assertEqual(r["channels"][1]["peak"], 0.5)

    def test_full_scale_fraction(self):
        self.write([-32768, 32767, 0, 0])
        self.assertEqual(analyze_music_wav(self.path)["channels"][0]["full_scale_fraction"], 0.5)

    def test_reject_empty(self):
        self.write([])
        with self.assertRaises(ValueError):
            analyze_music_wav(self.path)

    def test_reject_unsupported_width(self):
        self.write([128] * 10, width=1)
        with self.assertRaises(ValueError):
            analyze_music_wav(self.path)

    def test_reject_unsupported_rate(self):
        self.write([0] * 10, rate=4000)
        with self.assertRaises(ValueError):
            analyze_music_wav(self.path)

    def test_truncated_data(self):
        self.write([0] * 100)
        self.path.write_bytes(self.path.read_bytes()[:-20])
        with self.assertRaises(ValueError):
            analyze_music_wav(self.path)

    def test_repeatable_and_read_only(self):
        self.write([0, 8192, -8192] * 10)
        before = self.path.read_bytes()
        self.assertEqual(analyze_music_wav(self.path), analyze_music_wav(self.path))
        self.assertEqual(before, self.path.read_bytes())
