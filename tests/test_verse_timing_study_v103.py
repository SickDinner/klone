import io
import json
import math
import unittest
from contextlib import redirect_stdout

from klone.verse_timing_study import verse_timing_study, main


class VerseTimingStudyV103(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = verse_timing_study()
        cls.rows = {r["example"]: r for r in cls.report["observations"]}

    def test_inventory(self):
        self.assertEqual(self.report["schema"], "klone.verse_timing_study.v1")
        self.assertEqual(set(self.rows), {"even", "uneven", "even_regular"})

    def test_identical_counts_distinct_timing(self):
        a, b = self.rows["even"], self.rows["uneven"]
        for key in ("line", "written_vowel_groups", "illustrative_syllables",
                    "total_ms", "mean_duration_ms"):
            self.assertEqual(a[key], b[key])
        self.assertEqual(a["duration_cv"], 0)
        self.assertAlmostEqual(b["duration_population_sd_ms"], math.sqrt(11250))
        self.assertAlmostEqual(b["duration_cv"], math.sqrt(11250) / 250)

    def test_different_written_counts_same_timing(self):
        a, b = self.rows["even"], self.rows["even_regular"]
        self.assertEqual(a["illustrative_syllables"], b["illustrative_syllables"])
        self.assertEqual((a["written_vowel_groups"], b["written_vowel_groups"]), (3, 4))
        self.assertEqual([e["duration_ms"] for e in a["events"]],
                         [e["duration_ms"] for e in b["events"]])

    def test_contiguous_events(self):
        for row in self.rows.values():
            cursor = 0
            for event in row["events"]:
                self.assertEqual(event["start_ms"], cursor)
                self.assertGreater(event["duration_ms"], 0)
                cursor += event["duration_ms"]
            self.assertEqual(cursor, row["total_ms"])

    def test_uneven_reference(self):
        events = self.rows["uneven"]["events"]
        self.assertEqual([e["syllable"] for e in events], ["ra", "di", "o", "soi"])
        self.assertEqual([e["start_ms"] for e in events], [0, 150, 300, 700])
        self.assertEqual([e["duration_ms"] for e in events], [150, 150, 400, 300])

    def test_cli_repeatability(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main([]), 0)
        self.assertEqual(json.loads(out.getvalue()), self.report)
        self.assertEqual(verse_timing_study(), self.report)
