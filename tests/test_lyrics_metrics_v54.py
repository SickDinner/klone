import unittest
from klone.lyrics_metrics import analyze_lyrics, MAX_BYTES, MAX_LINES


class LyricsMetricsV54(unittest.TestCase):
    def test_sections_and_counts(self):
        r = analyze_lyrics("[Verse]\nPohjoinen yö\n[Chorus]\nYö yö\n")
        self.assertEqual(r["line_count"], 2)
        self.assertEqual(r["word_count"], 4)
        self.assertEqual(r["unique_word_count"], 2)
        self.assertEqual(r["type_token_ratio"], 0.5)
        self.assertEqual(r["sections"], [
            {"label": "Verse", "line_count": 1, "word_count": 2},
            {"label": "Chorus", "line_count": 1, "word_count": 2}])

    def test_repeated_lines_normalized(self):
        r = analyze_lyrics("YÖ  saapuu\nyö saapuu\nYö lähtee")
        self.assertEqual(r["repeated_line_occurrences"], 1)

    def test_unicode_equivalence(self):
        self.assertEqual(analyze_lyrics("yö"), analyze_lyrics("yo\u0308"))

    def test_unlabeled_text(self):
        self.assertEqual(analyze_lyrics("yö")["sections"][0]["label"], "unlabeled")

    def test_empty(self):
        r = analyze_lyrics("")
        self.assertIsNone(r["type_token_ratio"])
        self.assertEqual(r["sections"], [])

    def test_repeated_sections_not_merged(self):
        r = analyze_lyrics("[Chorus]\na\n[Chorus]\na")
        self.assertEqual(len(r["sections"]), 2)
        self.assertEqual(r["repeated_line_occurrences"], 1)

    def test_section_headers_excluded(self):
        r = analyze_lyrics("[Intro]\n[Verse 1]\nhello")
        self.assertEqual(r["word_count"], 1)
        self.assertEqual(r["sections"][0]["line_count"], 0)

    def test_reject_large_input(self):
        with self.assertRaises(ValueError):
            analyze_lyrics("a" * (MAX_BYTES + 1))

    def test_reject_many_lines(self):
        with self.assertRaises(ValueError):
            analyze_lyrics("a\n" * (MAX_LINES + 1))

    def test_no_lyric_text_in_metrics(self):
        r = analyze_lyrics("private synthetic phrase")
        self.assertNotIn("private synthetic phrase", str(r))

    def test_repeatable(self):
        self.assertEqual(analyze_lyrics("night falls"), analyze_lyrics("night falls"))
