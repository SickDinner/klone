"""Offline research fixtures: visual metrics, audio format and reproducibility.

No real user data, agents, model calls, external retrieval or runtime changes.
"""
import hashlib
import json
import math
import struct
import tempfile
import unittest
import wave
from pathlib import Path

from PIL import Image
from klone.art import _analyze_image_file


def canonical_digest(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def agreement(rows):
    """Agreement of two human-supplied categorical reviews, not accuracy."""
    if not rows or any(a not in {"yes", "no", "uncertain"} or
                       b not in {"yes", "no", "uncertain"} for a, b in rows):
        raise ValueError("invalid review rows")
    return sum(a == b for a, b in rows) / len(rows)


class ResearchReviewV41(unittest.TestCase):
    def test_agreement_preserves_disagreement(self):
        self.assertEqual(agreement([("yes", "yes"), ("yes", "no")]), 0.5)

    def test_uncertainty_is_not_agreement_with_yes(self):
        self.assertEqual(agreement([("uncertain", "yes")]), 0.0)

    def test_invalid_review_rejected(self):
        for rows in ([], [("yes", "unknown")]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                agreement(rows)


class ResearchManifestV43V48(unittest.TestCase):
    def test_digest_is_order_independent_for_object_keys(self):
        self.assertEqual(canonical_digest({"b": 2, "a": 1}),
                         canonical_digest({"a": 1, "b": 2}))

    def test_digest_changes_with_revision(self):
        self.assertNotEqual(canonical_digest({"revision": 1}),
                            canonical_digest({"revision": 2}))

    def test_nonfinite_measurement_rejected(self):
        with self.assertRaises(ValueError):
            canonical_digest({"value": math.nan})

    def test_array_order_retained(self):
        self.assertNotEqual(canonical_digest([1, 2]), canonical_digest([2, 1]))

    def test_unicode_round_trip(self):
        record = {"title": "Pohjoinen yö", "revision": 1}
        self.assertEqual(canonical_digest(record),
                         canonical_digest(json.loads(json.dumps(record))))


class VisualAudioV45(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def image_metrics(self, name, color, size=(64, 64)):
        path = self.root / (name + ".png")
        Image.new("RGB", size, color).save(path)
        return _analyze_image_file(path)

    def test_black_white_brightness(self):
        black = self.image_metrics("black", "black")
        white = self.image_metrics("white", "white")
        self.assertEqual(black["brightness_mean"], 0.0)
        self.assertEqual(white["brightness_mean"], 1.0)

    def test_solid_image_has_zero_contrast(self):
        result = self.image_metrics("gray", (128, 128, 128))
        self.assertEqual(result["contrast_stddev"], 0.0)
        self.assertEqual(result["symmetry_vertical"], 1.0)
        self.assertEqual(result["symmetry_horizontal"], 1.0)

    def test_visual_sample_bounded(self):
        result = self.image_metrics("large", "red", (512, 256))
        self.assertLessEqual(result["sample_width_px"], 128)
        self.assertLessEqual(result["sample_height_px"], 128)
        self.assertEqual(result["orientation"], "landscape")

    def test_image_metrics_repeatable(self):
        self.assertEqual(self.image_metrics("one", "blue"),
                         self.image_metrics("two", "blue"))

    def test_synthetic_audio_format_round_trip(self):
        path = self.root / "silence.wav"
        with wave.open(str(path), "wb") as out:
            out.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
            out.writeframes(struct.pack("<800h", *([0] * 800)))
        with wave.open(str(path), "rb") as source:
            self.assertEqual(source.getframerate(), 8000)
            self.assertEqual(source.getnframes(), 800)
            self.assertEqual(source.readframes(800), bytes(1600))

    def test_visual_report_json_round_trip(self):
        metrics = self.image_metrics("sample", "green")
        self.assertEqual(canonical_digest(metrics),
                         canonical_digest(json.loads(json.dumps(metrics))))
