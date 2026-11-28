import copy
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from klone.verse_reference_study import evaluate_verse_reference, main


class VerseReferenceStudyV73(unittest.TestCase):
    def test_exact_agreement(self):
        r = evaluate_verse_reference([{"line": "Kylmä tuuli", "reference_syllables": 4}])
        self.assertEqual(r["exact_match_fraction"], 1)
        self.assertEqual(r["mean_absolute_difference"], 0)

    def test_hiatus_disagreement(self):
        r = evaluate_verse_reference([{"line": "radio", "reference_syllables": 3}])
        self.assertEqual(r["rows"][0]["written_vowel_groups"], 2)
        self.assertEqual(r["mean_signed_difference"], -1)
        self.assertEqual(r["mean_absolute_difference"], 1)

    def test_missing_reference_not_zero(self):
        r = evaluate_verse_reference([{"line": "Yö"}, {"line": "Aamu", "reference_syllables": 2}])
        self.assertEqual(r["annotated_lines"], 1)
        self.assertEqual(r["unannotated_lines"], 1)
        self.assertIsNone(r["rows"][0]["difference"])
        self.assertEqual(r["exact_match_fraction"], 1)

    def test_all_missing(self):
        r = evaluate_verse_reference([{"line": "Yö"}])
        self.assertIsNone(r["exact_match_fraction"])
        self.assertIsNone(r["mean_absolute_difference"])
        self.assertIsNone(r["mean_signed_difference"])

    def test_signed_and_absolute_differences(self):
        r = evaluate_verse_reference([
            {"line": "radio", "reference_syllables": 3},
            {"line": "Aamu", "reference_syllables": 1},
        ])
        self.assertEqual(r["mean_signed_difference"], 0)
        self.assertEqual(r["mean_absolute_difference"], 1)
        self.assertEqual(r["difference_histogram"], {"-1": 1, "1": 1})

    def test_unicode_equivalence(self):
        self.assertEqual(evaluate_verse_reference([{"line": "yö"}]),
                         evaluate_verse_reference([{"line": "yo\u0308"}]))

    def test_invalid_annotations(self):
        for value in (False, 0, -1, 1.5, "3", 501):
            with self.subTest(value=value), self.assertRaises(ValueError):
                evaluate_verse_reference([{"line": "Yö", "reference_syllables": value}])

    def test_invalid_lines(self):
        for line in ("", "  ", "[Chorus]", "a\nb", "a" * 501, None):
            with self.subTest(line=line), self.assertRaises(ValueError):
                evaluate_verse_reference([{"line": line}])

    def test_bounds(self):
        for entries in ([], [None], [{"line": "Yö"}] * 1001):
            with self.subTest(size=len(entries)), self.assertRaises(ValueError):
                evaluate_verse_reference(entries)

    def test_no_source_text_and_no_mutation(self):
        entries = [{"line": "Pohjoinen tarina", "reference_syllables": 6}]
        before = copy.deepcopy(entries)
        result = evaluate_verse_reference(entries)
        self.assertNotIn("Pohjoinen tarina", json.dumps(result))
        self.assertEqual(entries, before)
        self.assertEqual(result, evaluate_verse_reference(entries))

    def test_cli_json(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "verse.json"
            entries = [{"line": "Yö", "reference_syllables": 1}]
            path.write_text(json.dumps(entries), encoding="utf-8")
            output = StringIO()
            with redirect_stdout(output):
                self.assertEqual(main([str(path)]), 0)
            self.assertEqual(json.loads(output.getvalue()), evaluate_verse_reference(entries))
