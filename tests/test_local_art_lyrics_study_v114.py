"""Analytic and boundary tests for the local lyric structure study."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from klone.local_art_lyrics_study import analyze_lyrics, main


class LocalArtLyricsStudyV114(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "private_lyrics.txt"

    def analyze(self, text):
        self.path.write_bytes(text.encode("utf-8"))
        return analyze_lyrics(self.path)

    def test_empty_text(self):
        r = self.analyze("")
        self.assertEqual(r["structure"]["lyric_line_count"], 0)
        self.assertEqual(r["structure"]["stanza_count"], 0)
        self.assertIsNone(r["lexical_metrics"]["type_token_ratio"])
        self.assertIsNone(r["line_end_metrics"]["distinct_end_word_suffix_match_fraction"])

    def test_sections_and_stanzas(self):
        r = self.analyze("[Intro]\nYö saapuu\n\n[Verse 1]\nTuuli kulkee\n\nVesi virtaa\n[Chorus]\nYö saapuu")
        s = r["structure"]
        self.assertEqual(s["lyric_line_count"], 4)
        self.assertEqual(s["stanza_count"], 4)
        self.assertEqual([x["kind"] for x in s["sections"]], ["intro","verse","chorus"])
        self.assertEqual([x["lyric_line_count"] for x in s["sections"]], [1,2,1])
        self.assertEqual([x["source_line"] for x in s["line_metrics"]], [2,5,7,9])

    def test_lexical_counts(self):
        m = self.analyze("Sana sana uusi\nUusi sana")["lexical_metrics"]
        self.assertEqual(m["word_count"], 5)
        self.assertEqual(m["distinct_word_forms"], 2)
        self.assertAlmostEqual(m["type_token_ratio"], .4)

    def test_unicode_normalization_and_bom(self):
        r = self.analyze("\ufeffYÖ! yö\nyo\u0308.")
        self.assertEqual(r["lexical_metrics"]["distinct_word_forms"], 1)
        self.assertEqual(r["lexical_metrics"]["word_count"], 3)

    def test_repeated_lines(self):
        m = self.analyze("Yö saapuu!\nYÖ SAAPUU\n\nYö saapuu\nTuuli kulkee")["lexical_metrics"]
        self.assertEqual(m["repeated_normalized_line_occurrences"], 2)
        self.assertEqual(m["repeated_normalized_line_fraction"], .5)

    def test_written_initials(self):
        m = self.analyze("Kylmä kivi kala\nVesi virtaa taas")["lexical_metrics"]
        self.assertEqual(m["adjacent_initial_matches"], 3)
        self.assertEqual(m["adjacent_word_pairs"], 4)
        self.assertEqual(m["adjacent_initial_match_fraction"], .75)

    def test_vowel_groups(self):
        r = self.analyze("Radio soi\nTuuli kulkee")
        self.assertEqual([x["written_vowel_group_count"] for x in r["structure"]["line_metrics"]], [3,4])

    def test_suffix_and_identical_words(self):
        m = self.analyze("Musta kissa\nValkea missä\nSininen kissa\nToinen kissa\nPieni pissa")["line_end_metrics"]
        self.assertEqual(m["eligible_adjacent_end_pairs"], 4)
        self.assertEqual(m["identical_end_word_pairs"], 1)
        self.assertEqual(m["distinct_end_word_suffix_matches"], 1)
        self.assertEqual(m["matching_line_pairs"], [{"source_lines":[4,5],"shared_suffix_chars":3}])

    def test_no_cross_stanza_end_pairs(self):
        m = self.analyze("Kissa\n\nPissa\n[Chorus]\nHissa")["line_end_metrics"]
        self.assertEqual(m["eligible_adjacent_end_pairs"], 0)
        self.assertIsNone(m["distinct_end_word_suffix_match_fraction"])

    def test_input_limits_and_encoding(self):
        with patch("klone.local_art_lyrics_study.MAX_BYTES", 2), self.assertRaises(ValueError):
            self.analyze("kolme")
        with patch("klone.local_art_lyrics_study.MAX_LINES", 1), self.assertRaises(ValueError):
            self.analyze("yö\npäivä")
        with patch("klone.local_art_lyrics_study.MAX_LINE_CHARS", 2), self.assertRaises(ValueError):
            self.analyze("kolme")
        self.path.write_bytes(b"\xff")
        with self.assertRaises(UnicodeDecodeError):
            analyze_lyrics(self.path)

    def test_fingerprint_no_raw_text_or_path(self):
        r = self.analyze("Uniikkisana kaikuu")
        self.assertEqual(r["source"]["sha256"], hashlib.sha256(self.path.read_bytes()).hexdigest())
        payload = json.dumps(r)
        self.assertNotIn("Uniikkisana", payload)
        self.assertNotIn("uniikkisana", payload)
        self.assertNotIn("private_lyrics", payload)
        self.assertEqual(r, analyze_lyrics(self.path))

    def test_cli(self):
        r = self.analyze("Yö saapuu")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main([str(self.path)]),0)
        self.assertEqual(json.loads(out.getvalue()),r)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            main([str(self.path.parent/"missing.txt")])
        self.assertEqual(caught.exception.code,2)
