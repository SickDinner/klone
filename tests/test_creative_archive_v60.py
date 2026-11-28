"""Regression tests for archived reports and synthetic abstract artwork."""
import copy
import tempfile
import unittest
from pathlib import Path

from PIL import Image
from klone.art import _analyze_image_file
from klone.song_report import render_song_html


def archived_report():
    return {
        "schema": "klone.song_report.v1",
        "lyrics": {
            "line_count": 2, "word_count": 4, "unique_word_count": 3,
            "type_token_ratio": 0.75, "repeated_line_occurrences": 0,
            "sections": [{"label": "Verse", "line_count": 2, "word_count": 4}],
            "limitations": ["archived lyric fixture"],
        },
        "audio": {
            "sample_rate_hz": 8000, "frames": 8000, "duration_seconds": 1.0,
            "channels": [{"channel": 0, "peak": 0.5, "rms": 0.25, "mean": 0,
                          "zero_fraction": 0, "full_scale_fraction": 0}],
            "limitations": ["archived audio fixture"],
        },
        "limitations": ["synthetic archive"],
    }


class ReportCompatibilityV60(unittest.TestCase):
    def test_legacy_report_renders(self):
        page = render_song_html(archived_report())
        self.assertIn("Verse", page)
        self.assertIn("Not recorded in this report version", page)

    def test_missing_is_distinct_from_null_and_zero(self):
        report = archived_report()
        report["lyrics"]["mattr"] = {"10": None, "25": 0.25}
        report["lyrics"]["adjacent_initial_matches"] = 0
        page = render_song_html(report)
        self.assertIn("Insufficient tokens", page)
        self.assertIn("Not recorded in this report version", page)
        self.assertIn("Adjacent initial-letter matches</th><td>0</td>", page)

    def test_missing_dynamics_marked(self):
        self.assertIn("Channel 1 dynamics</h2>", render_song_html(archived_report()))

    def test_render_does_not_change_archive(self):
        report = archived_report()
        before = copy.deepcopy(report)
        render_song_html(report)
        self.assertEqual(report, before)

    def test_archived_label_escaped(self):
        report = archived_report()
        report["lyrics"]["sections"][0]["label"] = "<script>"
        page = render_song_html(report)
        self.assertIn("&lt;script&gt;", page)
        self.assertNotIn("<script>", page)


class AbstractArtFixturesV60(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def metrics(self, name, image):
        path = self.root / (name + ".png")
        image.save(path)
        return _analyze_image_file(path)

    def test_uniform_gray_contrast(self):
        r = self.metrics("gray", Image.new("RGB", (64, 64), (128, 128, 128)))
        self.assertEqual(r["contrast_stddev"], 0)
        self.assertEqual(r["entropy"], 0)

    def test_mirror_changes_darkness_center(self):
        image = Image.new("RGB", (64, 64), "white")
        image.paste("black", (0, 0, 32, 64))
        a = self.metrics("left", image)
        b = self.metrics("right", image.transpose(Image.Transpose.FLIP_LEFT_RIGHT))
        self.assertAlmostEqual(a["center_of_mass_x"] + b["center_of_mass_x"], 1, places=3)
        self.assertEqual(a["brightness_mean"], b["brightness_mean"])

    def test_colorfulness_neutral_vs_color(self):
        gray = self.metrics("gray", Image.new("RGB", (64, 64), (128, 128, 128)))
        red = self.metrics("red", Image.new("RGB", (64, 64), "red"))
        self.assertEqual(gray["colorfulness"], 0)
        self.assertGreater(red["colorfulness"], gray["colorfulness"])

    def test_asymmetric_abstract_composition(self):
        image = Image.new("RGB", (64, 64), "white")
        image.paste("black", (0, 0, 16, 64))
        result = self.metrics("asymmetry", image)
        self.assertLess(result["symmetry_vertical"], result["symmetry_horizontal"])

    def test_repeated_metrics_are_equal(self):
        image = Image.new("RGB", (64, 64), "blue")
        self.assertEqual(self.metrics("one", image), self.metrics("two", image))
