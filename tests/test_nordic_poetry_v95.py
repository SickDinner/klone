import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from klone.nordic_poetry import DEMO, main, poetry_study


class NordicPoetryV95(unittest.TestCase):
    def test_harmony_categories(self):
        r = poetry_study("yö talo äiti tie kesätalo xkz")
        self.assertEqual(r["vowel_harmony_word_counts"], {
            "front": 2, "back": 1, "mixed_front_back": 1,
            "neutral_only": 1, "no_recognized_vowel": 1,
        })

    def test_initial_patterns(self):
        r = poetry_study("Kuu kulkee kultarannan\nSana sana sataa")
        self.assertEqual([x["distinct_word_initial_matches"] for x in r["lines"]], [2, 1])
        self.assertEqual([x["adjacent_word_pairs"] for x in r["lines"]], [2, 2])

    def test_written_rhythm(self):
        r = poetry_study("Kuu kulkee kultarannan")
        self.assertEqual(r["lines"][0]["written_vowel_groups"], 7)

    def test_stanza_boundaries(self):
        r = poetry_study("[Verse]\nKuu kulkee\nKuu loistaa\n\nYö alkaa\n[Chorus]\nYö jatkuu")
        self.assertEqual([x["line_count"] for x in r["stanzas"]], [2, 1, 1])
        self.assertEqual(len(r["within_stanza_adjacent_lines"]), 1)

    def test_exact_overlap(self):
        r = poetry_study("Yö yllä järven jäällä\nYö yllä metsän säällä")
        pair = r["within_stanza_adjacent_lines"][0]
        self.assertEqual(pair["shared_word_types"], 2)
        self.assertEqual(pair["shared_prefix_words"], 2)
        self.assertAlmostEqual(pair["word_type_jaccard"], 1/3)

    def test_unicode_normalization(self):
        self.assertEqual(poetry_study("YÖ ÄITI"), poetry_study("yo\u0308 a\u0308iti"))

    def test_empty_and_bounds(self):
        self.assertEqual(poetry_study("[Verse]\n123 !!!\n")["line_count"], 0)
        for value in (None, "a" * 256001, "a\n" * 10001):
            with self.assertRaises(ValueError):
                poetry_study(value)

    def test_no_source_words(self):
        r = poetry_study("salaperainen ainutkertainen")
        self.assertNotIn("salaperainen", json.dumps(r))
        self.assertEqual(r["word_count"], 2)

    def test_cli_demo_and_file(self):
        expected = poetry_study(DEMO)
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main(["--demo"]), 0)
        self.assertEqual(json.loads(out.getvalue()), expected)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "poem.txt"
            path.write_text(DEMO, encoding="utf-8")
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(main(["--lyrics", str(path)]), 0)
            self.assertEqual(json.loads(out.getvalue()), expected)
