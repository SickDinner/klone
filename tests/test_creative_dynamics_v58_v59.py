import math
import struct
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from klone.music_pcm_metrics import analyze_music_wav
from klone.lyrics_metrics import analyze_lyrics
from klone.song_report import song_report, render_song_html


class MusicDynamicsV58(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.path = self.root / "fixture.wav"

    def write(self, samples):
        with wave.open(str(self.path), "wb") as out:
            out.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
            out.writeframes(struct.pack("<" + "h" * len(samples), *samples))

    def test_constant_signal(self):
        self.write([8192] * 16000)
        result = analyze_music_wav(self.path)["channels"][0]
        self.assertEqual(result["crest_factor_db"], 0)
        self.assertEqual(result["one_second_rms"], {
            "full_window_count": 2, "excluded_tail_frames": 0,
            "minimum": 0.25, "maximum": 0.25, "p10": 0.25, "p90": 0.25})

    def test_dynamic_fixture(self):
        self.write([0] * 8000 + [16384] * 8000)
        result = analyze_music_wav(self.path)["channels"][0]
        self.assertAlmostEqual(result["crest_factor_db"], 20 * math.log10(math.sqrt(2)), places=7)
        self.assertEqual(result["one_second_rms"]["p10"], 0)
        self.assertEqual(result["one_second_rms"]["p90"], 0.5)

    def test_silence_and_short_tail(self):
        self.write([0] * 7999)
        result = analyze_music_wav(self.path)["channels"][0]
        self.assertIsNone(result["crest_factor_db"])
        self.assertIsNone(result["one_second_rms"]["p10"])
        self.assertEqual(result["one_second_rms"]["excluded_tail_frames"], 7999)

    def test_tail_not_included_in_window_statistics(self):
        self.write([0] * 8000 + [32767] * 4000)
        result = analyze_music_wav(self.path)["channels"][0]
        self.assertEqual(result["one_second_rms"]["maximum"], 0)
        self.assertGreater(result["rms"], 0)

    def test_chunk_independence(self):
        self.write([0, 8192, -16384] * 8001)
        expected = analyze_music_wav(self.path)
        with patch("klone.music_pcm_metrics.CHUNK_FRAMES", 127):
            self.assertEqual(analyze_music_wav(self.path), expected)

    def test_html_contains_new_metrics(self):
        self.write([8192] * 8000)
        lyrics = self.root / "lyrics.txt"
        lyrics.write_text("ilta\nsilta", encoding="utf-8")
        page = render_song_html(song_report(lyrics, self.path))
        self.assertIn("Crest factor", page)
        self.assertIn("Written line endings", page)
        self.assertIn("suffix_3", page)


class WrittenEndPatternsV59(unittest.TestCase):
    def patterns(self, text, distance=1):
        return analyze_lyrics(text)["orthographic_end_patterns"][str(distance)]

    def test_adjacent_suffix_matches(self):
        r = self.patterns("ilta\nsilta")
        self.assertEqual(r, {"eligible_pairs": 1, "identical_end_words": 0,
                             "suffix_2": 1, "suffix_3": 1, "suffix_4": 1})

    def test_alternating_endings(self):
        text = "ilta\nmaa\nsilta\nsaa"
        self.assertEqual(self.patterns(text)["suffix_2"], 0)
        self.assertEqual(self.patterns(text, 2)["suffix_2"], 2)

    def test_identical_end_words_separate(self):
        r = self.patterns("ilta\nILTA!")
        self.assertEqual(r["identical_end_words"], 1)
        self.assertEqual(r["suffix_2"], 0)

    def test_section_boundary(self):
        self.assertEqual(self.patterns("[Verse]\nilta\n[Chorus]\nsilta")["eligible_pairs"], 0)

    def test_punctuation_and_nonword_line(self):
        r = self.patterns("ilta!\nsilta?\n...\nilta")
        self.assertEqual(r["eligible_pairs"], 1)

    def test_no_ending_text_exported(self):
        self.assertNotIn("suklaasilta", str(self.patterns("ilta\nsuklaasilta")))
