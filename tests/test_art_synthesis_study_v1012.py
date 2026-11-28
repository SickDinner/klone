"""Tests for the fixed creative-art synthesis report."""
import hashlib
import io
import json
import unittest
from collections import Counter
from contextlib import redirect_stdout

from klone.art_synthesis_study import synthesis_study, main
from klone.verse_timing_study import verse_timing_study
from klone.perceptual_color_study import color_study
from klone.advanced_color_study import advanced_color_study
from klone.spatial_composition_study import spatial_study
from klone.temporal_rhythm_study import rhythm_study
from klone.musical_spectrum_study import spectrum_study
from klone.crossmodal_art_structure import crossmodal_study
from klone.aesthetic_catalog_study import aesthetic_catalog
from klone.aesthetic_review_study import review_study


class ArtSynthesisStudyV1012(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = synthesis_study()
        cls.summary = cls.report["summary"]
        cls.studies = {r["version"]: r for r in cls.report["studies"]}

    def test_inventory(self):
        self.assertEqual(len(self.report["studies"]), 9)
        self.assertEqual(self.summary["study_count"], 9)
        self.assertEqual(list(self.studies), ["10."+str(i) for i in range(3,12)])
        self.assertEqual(self.summary["observation_counts_by_version"],
                         {"10.3":3,"10.4":5,"10.5":5,"10.6":7,"10.7":9,"10.8":9})

    def test_source_payloads_unchanged(self):
        sources = (verse_timing_study, color_study, advanced_color_study,
                   spatial_study, rhythm_study, spectrum_study, crossmodal_study,
                   aesthetic_catalog, review_study)
        for i, source in enumerate(sources, 3):
            row = self.studies["10."+str(i)]
            self.assertEqual(row["payload"], source())
            self.assertEqual(row["source_schema"], row["payload"]["schema"])
            self.assertTrue(row["payload"]["limitations"])

    def test_payload_fingerprints(self):
        for row in self.studies.values():
            encoded = json.dumps(row["payload"], sort_keys=True, separators=(",", ":"),
                                 ensure_ascii=True, allow_nan=False).encode("ascii")
            self.assertEqual(row["payload_sha256"], hashlib.sha256(encoded).hexdigest())

    def test_verse_timing_preserved(self):
        rows = {r["example"]:r for r in self.summary["verse_timing_examples"]}
        self.assertEqual(len(rows),3)
        self.assertEqual(rows["even"]["total_ms"],rows["uneven"]["total_ms"])
        self.assertEqual(rows["even"]["illustrative_syllables"],
                         rows["uneven"]["illustrative_syllables"])
        self.assertEqual(rows["even"]["duration_cv"],0)
        self.assertGreater(rows["uneven"]["duration_cv"],0)

    def test_color_model_disagreement(self):
        self.assertEqual(self.summary["color_maximal_examples"],
                         {"delta_e_76":["green_change"],
                          "delta_e_2000":["green_change"],
                          "oklab_distance":["dark_gray"]})

    def test_cross_domain_counts(self):
        self.assertEqual(self.summary["cross_domain_profile_count"],25)
        self.assertEqual(self.summary["cross_domain_pair_count"],207)
        pairs = self.studies["10.9"]["payload"]["cross_domain_comparisons"]
        self.assertEqual(self.summary["exact_descriptor_match_counts"],
                         dict(Counter(k for p in pairs for k in p["exact_descriptor_matches"])))
        self.assertEqual(self.summary["undefined_descriptor_counts"],
                         {"local_transition_fraction":144})

    def test_catalog_counts(self):
        self.assertEqual(self.summary["catalog_record_count"],25)
        self.assertEqual(self.summary["catalog_revision_count"],50)
        self.assertEqual(self.summary["catalog_complete_match_count"],6)

    def test_review_accounting(self):
        self.assertEqual(self.summary["review_status_counts"],
                         {"supported_in_fixtures":4,"contradicted_in_fixtures":1,
                          "not_assessed":2})
        self.assertEqual(self.summary["review_evidence_item_count"],27)

    def test_scope_limits(self):
        scope = self.report["scope"]
        self.assertIsNone(scope["overall_aesthetic_score"])
        self.assertFalse(scope["empirical_observer_validation"])
        self.assertFalse(scope["verse_and_color_in_common_comparisons"])
        self.assertEqual(scope["cross_domain_coverage"],["spatial","rhythm","spectrum"])

    def test_cli_full_and_summary(self):
        for args in ([],["--summary"]):
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(main(args),0)
            expected = self.report if not args else {
                k:self.report[k] for k in ("schema","summary","scope","limitations")}
            self.assertEqual(json.loads(out.getvalue()),expected)

    def test_repeatability(self):
        self.assertEqual(synthesis_study(), self.report)
        self.assertEqual(json.loads(json.dumps(self.report, allow_nan=False)),self.report)
