"""Synthetic, reproducible fixtures for the three creative research tracks."""
import cmath
import math
import struct
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from klone.artwork_color_metrics import artwork_color_metrics
from klone.music_clip_spectrum import music_clip_spectrum, _fft, WINDOW, MAX_WINDOWS
from klone.written_verse_rhythm import written_verse_rhythm


class CreativeColorV61(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "art.png"

    def test_equal_color_regions(self):
        image = Image.new("RGB", (64, 64), "red")
        image.paste("blue", (32, 0, 64, 64))
        image.save(self.path)
        r = artwork_color_metrics(self.path)
        self.assertEqual(r["occupied_rgb_bins"], 2)
        self.assertEqual(r["neutral_fraction"], 0)
        self.assertEqual([x["fraction"] for x in r["dominant_bins"]], [0.5, 0.5])

    def test_transparency_on_white(self):
        Image.new("RGBA", (32, 32), (255, 0, 0, 0)).save(self.path)
        r = artwork_color_metrics(self.path)
        self.assertEqual(r["neutral_fraction"], 1)
        self.assertEqual(r["dominant_bins"][0]["rgb_bin"], [7, 7, 7])

    def test_sampling_bound_and_unchanged_file(self):
        Image.new("RGB", (256, 128), "gray").save(self.path)
        original = self.path.read_bytes()
        r = artwork_color_metrics(self.path)
        self.assertEqual(r["sample_dimensions"], [128, 64])
        self.assertEqual(original, self.path.read_bytes())
        self.assertEqual(r, artwork_color_metrics(self.path))

    def test_pixel_limit(self):
        Image.new("RGB", (32, 32)).save(self.path)
        with patch("klone.artwork_color_metrics.MAX_PIXELS", 100):
            with self.assertRaises(ValueError):
                artwork_color_metrics(self.path)


class MusicSpectrumV62(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "music.wav"

    def write(self, samples, rate=8192):
        with wave.open(str(self.path), "wb") as out:
            out.setparams((1, 2, rate, 0, "NONE", "not compressed"))
            out.writeframes(struct.pack("<" + "h" * len(samples), *samples))

    def test_fft_against_direct_dft(self):
        x = [1, 3, 0, -2, 4, 1, -1, 0]
        expected = [sum(v * cmath.exp(-2j * math.pi * k * i / len(x))
                        for i, v in enumerate(x)) for k in range(len(x))]
        for actual, reference in zip(_fft(x), expected):
            self.assertAlmostEqual(abs(actual - reference), 0, places=9)

    def test_synthetic_musical_tone(self):
        self.write([round(8000 * math.sin(2 * math.pi * 1000 * i / 8192))
                    for i in range(WINDOW)])
        c = music_clip_spectrum(self.path)["channels"][0]
        self.assertAlmostEqual(c["spectral_centroid_hz"], 1000, delta=0.1)
        self.assertGreater(c["band_fractions"][2]["fraction"], 0.999)

    def test_silence_is_undefined(self):
        self.write([0] * WINDOW)
        c = music_clip_spectrum(self.path)["channels"][0]
        self.assertIsNone(c["spectral_centroid_hz"])
        self.assertTrue(all(b["fraction"] is None for b in c["band_fractions"]))

    def test_window_cap(self):
        self.write([0] * (WINDOW * (MAX_WINDOWS + 1)))
        with patch("klone.music_clip_spectrum.MAX_WINDOWS", 2):
            r = music_clip_spectrum(self.path)
            self.assertEqual(r["analyzed_frames"], 2 * WINDOW)

    def test_short_clip_rejected(self):
        self.write([0] * (WINDOW - 1))
        with self.assertRaises(ValueError):
            music_clip_spectrum(self.path)


class WrittenRhythmV63(unittest.TestCase):
    def test_finnish_written_groups(self):
        r = written_verse_rhythm("[Verse]\nPohjoinen yö\nKylmä tuuli")
        self.assertEqual(r["written_vowel_groups_per_line"], [4, 4])
        self.assertEqual(r["vowel_group_histogram"], {"4": 2})
        self.assertEqual(r["equal_adjacent_counts"], 1)

    def test_empty_text(self):
        self.assertIsNone(written_verse_rhythm("[Intro]\n")["mean_vowel_groups"])

    def test_unicode_normalization(self):
        self.assertEqual(written_verse_rhythm("yö"), written_verse_rhythm("yo\u0308"))

    def test_word_boundaries(self):
        self.assertEqual(written_verse_rhythm("aa aa")["written_vowel_groups_per_line"], [2])

    def test_does_not_claim_syllable_count(self):
        r = written_verse_rhythm("ruoan")
        self.assertNotIn("syllable_count", r)
        self.assertIn("Not syllabification", " ".join(r["limitations"]))
