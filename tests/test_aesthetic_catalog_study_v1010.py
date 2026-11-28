"""Regression tests for the fixed synthetic art catalog."""
import hashlib
import io
import json
import unittest
from contextlib import redirect_stdout

from klone.aesthetic_catalog_study import aesthetic_catalog, main
from klone.crossmodal_art_structure import profiles


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True,
        separators=(",", ":"), ensure_ascii=True,
        allow_nan=False).encode("ascii")).hexdigest()


class AestheticCatalogStudyV1010(unittest.TestCase):
    def setUp(self):
        self.report = aesthetic_catalog()
        self.records = {r["fixture_id"]: r for r in self.report["records"]}

    def test_inventory(self):
        self.assertEqual(len(self.report["records"]), 25)
        self.assertEqual(len(self.records), 25)
        self.assertEqual(sum(len(r["revisions"]) for r in self.records.values()), 50)

    def test_source_fingerprints(self):
        for r in self.records.values():
            self.assertEqual(r["source_sha256"], digest({
                "schema": r["source_schema"], "fixture": r["source_fixture"]}))

    def test_revision_fingerprints(self):
        for r in self.records.values():
            for revision in r["revisions"]:
                body = {k:v for k,v in revision.items() if k != "revision_sha256"}
                self.assertEqual(revision["revision_sha256"], digest(body))

    def test_revision_links(self):
        for r in self.records.values():
            first, second = r["revisions"]
            self.assertEqual([first["revision"],second["revision"]], [1,2])
            self.assertIsNone(first["previous_revision_sha256"])
            self.assertEqual(second["previous_revision_sha256"],first["revision_sha256"])
            self.assertNotEqual(first["revision_sha256"],second["revision_sha256"])

    def test_common_descriptors_preserved(self):
        for p in profiles():
            r = self.records[p["domain"] + ":" + p["example"]]
            first, second = r["revisions"]
            self.assertEqual(first["common_descriptors"],p["features"])
            self.assertEqual(second["common_descriptors"],p["features"])
            self.assertEqual(first["domain_context"],{})
            self.assertEqual(len(second["domain_context"]),4)

    def test_collision_inventory(self):
        collisions = self.report["cross_domain_descriptor_collisions"]
        self.assertEqual(len(collisions),6)
        for c in collisions:
            self.assertTrue(c["distinct_source_fingerprints"])
            self.assertNotEqual(c["first_fixture_id"],c["second_fixture_id"])
            self.assertEqual(len(c["matching_descriptors"]),3)
            self.assertEqual(c["interpretation"],"descriptor_match_only")

    def test_rhythm_context_distinguishes_collision(self):
        regular = self.records["rhythm:regular_quarters"]["revisions"]
        alternate = self.records["rhythm:alternating_gaps"]["revisions"]
        self.assertEqual(regular[0]["common_descriptors"],alternate[0]["common_descriptors"])
        self.assertEqual(regular[1]["domain_context"]["minimal_period_steps"],4)
        self.assertEqual(alternate[1]["domain_context"]["minimal_period_steps"],8)

    def test_spectrum_context_distinguishes_collision(self):
        soft = self.records["spectrum:soft_harmonics"]["revisions"]
        bright = self.records["spectrum:bright_harmonics"]["revisions"]
        self.assertEqual(soft[0]["common_descriptors"],bright[0]["common_descriptors"])
        self.assertNotEqual(soft[1]["domain_context"]["harmonic_power_entropy_bits"],
                            bright[1]["domain_context"]["harmonic_power_entropy_bits"])

    def test_missingness_preserved(self):
        r = self.records["spectrum:silence"]["revisions"][1]
        self.assertIsNone(r["common_descriptors"]["local_transition_fraction"])
        self.assertIsNone(r["domain_context"]["power_centroid_hz"])
        self.assertEqual(r["domain_context"]["ideal_cycle_rms"],0)
        r = self.records["spatial:empty"]["revisions"][1]
        self.assertIsNone(r["domain_context"]["normalized_centroid_offset"])
        r = self.records["rhythm:silent"]["revisions"][1]
        self.assertIsNone(r["domain_context"]["gap_entropy_bits"])

    def test_repeatability_and_cli(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main([]),0)
        self.assertEqual(json.loads(out.getvalue()),self.report)
        self.assertEqual(aesthetic_catalog(),self.report)
