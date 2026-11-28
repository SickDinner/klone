import random
import struct
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from klone.music_pcm_metrics import analyze_music_wav, CHUNK_FRAMES
from klone.lyrics_metrics import analyze_lyrics, moving_average_ttr


class StreamingMusicV56(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "music.wav"

    def write(self, frames, rate=8000):
        with wave.open(str(self.path), "wb") as out:
            out.setparams((2, 2, rate, 0, "NONE", "not compressed"))
            block = struct.pack("<hh", -16384, 8192)
            for start in range(0, frames, CHUNK_FRAMES):
                out.writeframesraw(block * min(CHUNK_FRAMES, frames - start))

    def test_longer_than_old_frame_limit(self):
        self.write(480001)
        result = analyze_music_wav(self.path)
        self.assertEqual(result["frames"], 480001)
        self.assertEqual(result["channels"][0]["mean"], -0.5)
        self.assertEqual(result["channels"][1]["rms"], 0.25)

    def test_chunk_size_independence(self):
        self.write(CHUNK_FRAMES + 3)
        expected = analyze_music_wav(self.path)
        with patch("klone.music_pcm_metrics.CHUNK_FRAMES", 137):
            self.assertEqual(analyze_music_wav(self.path), expected)

    def test_truncation_after_first_chunk(self):
        self.write(CHUNK_FRAMES + 100)
        self.path.write_bytes(self.path.read_bytes()[:-4])
        with self.assertRaises(ValueError):
            analyze_music_wav(self.path)

    def test_duration_limit(self):
        self.write(8001)
        with patch("klone.music_pcm_metrics.MAX_DURATION_SECONDS", 1):
            with self.assertRaises(ValueError):
                analyze_music_wav(self.path)

    def test_source_unchanged(self):
        self.write(CHUNK_FRAMES + 1)
        before = self.path.read_bytes()
        analyze_music_wav(self.path)
        self.assertEqual(before, self.path.read_bytes())


class LexicalResearchV57(unittest.TestCase):
    def test_known_mattr(self):
        self.assertEqual(moving_average_ttr(["a", "a", "b", "c"], 2),
                         round(5 / 6, 8))

    def test_short_text_explicitly_unavailable(self):
        self.assertIsNone(moving_average_ttr(["a"], 2))
        self.assertIsNone(analyze_lyrics("pohjoinen yö")["mattr"]["10"])

    def test_repeated_and_unique_tokens(self):
        self.assertEqual(moving_average_ttr(["a"] * 10, 5), 0.2)
        self.assertEqual(moving_average_ttr(list("abcdefghij"), 5), 1.0)

    def test_invalid_windows(self):
        for value in (0, -1, True, 1.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                moving_average_ttr(["a"], value)

    def test_matches_brute_force_reference(self):
        rng = random.Random(72)
        for length in (10, 25, 53):
            tokens = [rng.choice("abcdef") for _ in range(length)]
            for window in (1, 5, 10):
                with self.subTest(length=length, window=window):
                    expected = round(sum(len(set(tokens[i:i+window]))
                                         for i in range(length-window+1))
                                     / (window*(length-window+1)), 8)
                    self.assertEqual(moving_average_ttr(tokens, window), expected)

    def test_orthographic_patterns_and_line_boundaries(self):
        report = analyze_lyrics("[Verse]\nPimeä pohjoinen palaa\nPäivä vaihtuu\n")
        self.assertEqual(report["line_word_counts"], [3, 2])
        self.assertEqual(report["adjacent_initial_matches"], 2)
        self.assertEqual(report["adjacent_word_pairs"], 3)

    def test_no_initial_match_for_digits(self):
        report = analyze_lyrics("1 1 2")
        self.assertEqual(report["adjacent_word_pairs"], 0)
        self.assertEqual(report["adjacent_initial_matches"], 0)

    def test_fixed_window_output(self):
        report = analyze_lyrics(" ".join(["yö"] * 50))
        self.assertEqual(report["mattr"], {"10": 0.1, "25": 0.04, "50": 0.02})
