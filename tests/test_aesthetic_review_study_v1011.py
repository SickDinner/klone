"""Tests for deterministic synthetic art review."""
import io
import json
import unittest
from contextlib import redirect_stdout

from klone.aesthetic_review_study import review_study, main
from klone.aesthetic_catalog_study import aesthetic_catalog
from klone.advanced_color_study import advanced_color_study


class AestheticReviewStudyV1011(unittest.TestCase):
    def setUp(self):
        self.report = review_study()
        self.by_id = {r["id"]: r for r in self.report["reviews"]}

    def test_inventory(self):
        self.assertEqual(len(self.by_id), 7)
        self.assertEqual(len(self.report["reviews"]), 7)
        self.assertEqual(self.report["status_counts"], {
            "supported_in_fixtures": 4, "contradicted_in_fixtures": 1,
            "not_assessed": 2})

    def test_rhythm_claim(self):
        r = self.by_id["rhythm_period_collision"]
        self.assertEqual(r["status"], "supported_in_fixtures")
        self.assertEqual([e["value"] for e in r["evidence"][:2]], [4,8])

    def test_spectrum_claim(self):
        r = self.by_id["spectral_occupancy_collision"]
        self.assertEqual(r["status"], "supported_in_fixtures")
        self.assertAlmostEqual(r["evidence"][0]["value"], 1.0446850537847605)
        self.assertEqual(r["evidence"][1]["value"], 2)

    def test_missing_not_zero(self):
        r = self.by_id["undefined_not_zero"]
        self.assertEqual(r["status"], "supported_in_fixtures")
        self.assertIsNone(r["evidence"][0]["value"])
        self.assertEqual(r["evidence"][1]["value"], 0)

    def test_color_disagreement(self):
        r = self.by_id["color_model_disagreement"]
        self.assertEqual(r["status"], "contradicted_in_fixtures")
        self.assertEqual([e["maximal_examples"] for e in r["evidence"]],
                         [["green_change"], ["green_change"], ["dark_gray"]])
        for e in r["evidence"]:
            self.assertEqual(e["values"], {x["example"]: x[e["metric"]]
                            for x in advanced_color_study()["observations"]})

    def test_revision_evidence_resolves(self):
        records = {r["fixture_id"]: r for r in aesthetic_catalog()["records"]}
        for review in self.report["reviews"]:
            for e in review["evidence"]:
                if "revision" not in e:
                    continue
                rev = records[e["fixture_id"]]["revisions"][e["revision"]-1]
                group, key = e["field"].split(".")
                self.assertEqual(rev[group][key], e["value"])
                self.assertEqual(rev["revision_sha256"], e["revision_sha256"])

    def test_source_distinction(self):
        r = self.by_id["source_distinction"]
        self.assertEqual(r["status"], "supported_in_fixtures")
        self.assertEqual(len(r["evidence"]), 6)
        records = {r["fixture_id"]: r for r in aesthetic_catalog()["records"]}
        for e in r["evidence"]:
            for side in ("first","second"):
                self.assertEqual(e[side+"_source_sha256"],
                                 records[e[side+"_fixture_id"]]["source_sha256"])
            self.assertNotEqual(e["first_source_sha256"], e["second_source_sha256"])

    def test_unassessed_claims(self):
        for key in ("aesthetic_preference","crossmodal_perception"):
            r = self.by_id[key]
            self.assertEqual(r["status"], "not_assessed")
            self.assertEqual(r["evidence"], [])
            self.assertTrue(r["scope_limit"])

    def test_scope_limits(self):
        for r in self.report["reviews"]:
            self.assertTrue(r["scope_limit"])
            self.assertTrue(r["claim"])
        self.assertEqual(sum(self.report["status_counts"].values()), 7)

    def test_repeatability_and_cli(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main([]), 0)
        self.assertEqual(json.loads(out.getvalue()), self.report)
        self.assertEqual(review_study(), self.report)
