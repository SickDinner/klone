"""Tests for controlled art descriptor validation."""
from contextlib import redirect_stdout
import io
import json
import unittest
from unittest.mock import patch

from klone.art_metric_validation import main, validation_study
from klone.local_art_image_study import analyze_image


class ArtMetricValidationV117(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = validation_study()
        cls.checks = {c["id"]:c for c in cls.report["checks"]}

    def test_inventory(self):
        self.assertEqual(self.report["schema"],"klone.art_metric_validation.v1")
        self.assertEqual(len(self.checks),10)
        self.assertEqual(self.report["status_counts"],{"passed":10})
        self.assertEqual({d:sum(c["domain"]==d for c in self.checks.values())
                          for d in ("image","audio","lyrics")},
                         {"image":3,"audio":3,"lyrics":4})

    def test_image_distribution_vs_structure(self):
        self.assertEqual(self.checks["image_equal_distribution"]["observed"],
                         {"mean_difference":0,"contrast_difference":0,"entropy_difference":0})
        self.assertAlmostEqual(self.checks["image_reflection_distinguishes"]["observed"]["split"],1)
        self.assertEqual(self.checks["image_reflection_distinguishes"]["observed"]["centered"],0)
        for v in self.checks["image_integer_replication"]["observed"].values():
            self.assertAlmostEqual(v,0)

    def test_audio_gain(self):
        r = self.checks["audio_exact_gain"]["observed"]
        self.assertAlmostEqual(r["peak_ratio"],2)
        self.assertAlmostEqual(r["rms_ratio"],2)
        self.assertAlmostEqual(r["crest_difference"],0)
        for v in self.checks["audio_centroid_gain_invariance"]["observed"].values():
            self.assertAlmostEqual(v,2048)

    def test_missingness(self):
        self.assertEqual(self.checks["audio_silence_missingness"]["observed"],
                         {"rms":0,"crest_factor":None,"centroid":None,"bands":None})
        self.assertEqual(self.checks["lyrics_empty_missingness"]["observed"],
                         {"words":0,"ttr":None,"initial_fraction":None})

    def test_lyrics_sensitivity(self):
        self.assertEqual(self.checks["lyrics_normalization"]["observed"],
                         {"equal_lexical_metrics":True,"equal_source":False})
        self.assertEqual(self.checks["lyrics_ttr_length_sensitivity"]["observed"],
                         {"base_ttr":1,"repeated_ttr":.5,
                          "distinct_difference":0,"repeated_line_fraction":.5})
        self.assertEqual(self.checks["lyrics_suffix_vs_identity"]["observed"],
                         {"eligible":3,"distinct_matches":1,"identical":1})

    def test_scope(self):
        self.assertTrue(self.report["scope"]["synthetic_only"])
        self.assertFalse(self.report["scope"]["empirical_observer_validation"])
        self.assertIsNone(self.report["scope"]["overall_quality_score"])
        self.assertTrue(all(c["scope"] for c in self.checks.values()))
        self.assertTrue(self.report["limitations"])

    def test_deterministic_cli(self):
        self.assertEqual(validation_study(),self.report)
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main([]),0)
        self.assertEqual(json.loads(out.getvalue()),self.report)

    def test_detect_perturbed_metric_and_nonzero_exit(self):
        def changed(path):
            r = analyze_image(path)
            r["metrics"]["left_right_luminance_reflection_error"] = .25
            return r
        out = io.StringIO()
        with patch("klone.art_metric_validation.analyze_image",side_effect=changed):
            with redirect_stdout(out):
                self.assertEqual(main([]),1)
        r = json.loads(out.getvalue())
        self.assertEqual(r["status_counts"],{"failed":1,"passed":9})
        self.assertEqual([c["id"] for c in r["checks"] if c["status"]=="failed"],
                         ["image_reflection_distinguishes"])
