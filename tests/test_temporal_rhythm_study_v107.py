"""Analytic and metamorphic tests for fixed musical pulse patterns."""
import io
import json
import unittest
from contextlib import redirect_stdout

from klone.temporal_rhythm_study import PATTERNS, rhythm_metrics, rhythm_study, main


class TemporalRhythmStudyV107(unittest.TestCase):
    def test_regular_quarters(self):
        m = rhythm_metrics("1000100010001000")
        self.assertEqual(m["onset_count"], 4)
        self.assertEqual(m["onset_density"], .25)
        self.assertEqual(m["cyclic_interonset_gaps_steps"], [4]*4)
        self.assertEqual(m["gap_entropy_bits"], 0)
        self.assertEqual(m["gap_coefficient_of_variation"], 0)
        self.assertEqual(m["minimal_period_steps"], 4)
        self.assertEqual(m["repetitions"], 4)
        self.assertEqual(m["cyclic_onset_overlap_counts"], [4,0,0,0]*4)

    def test_clustered_gaps(self):
        m = rhythm_metrics("1111000000000000")
        self.assertEqual(m["cyclic_interonset_gaps_steps"], [1,1,1,13])
        self.assertAlmostEqual(m["gap_entropy_bits"], .8112781244591328)
        self.assertEqual(m["gap_mean_steps"], 4)
        self.assertEqual(m["minimal_period_steps"], 16)
        self.assertEqual(m["cyclic_transition_count"], 2)

    def test_same_density_different_structure(self):
        a,b,c,d = [rhythm_metrics(p) for _,p in PATTERNS[:4]]
        self.assertEqual(len({m["binary_entropy_bits"] for m in (a,b,c,d)}), 1)
        self.assertEqual(len({m["canonical_rotation"] for m in (a,b,c,d)}), 4)
        self.assertEqual(len({m["gap_entropy_bits"] for m in (a,b,c,d)}), 4)

    def test_alternating_gaps(self):
        m = rhythm_metrics("1010000010100000")
        self.assertEqual(m["cyclic_interonset_gaps_steps"], [2,6,2,6])
        self.assertEqual(m["gap_entropy_bits"], 1)
        self.assertEqual(m["gap_coefficient_of_variation"], .5)
        self.assertEqual(m["minimal_period_steps"], 8)

    def test_rotational_invariance(self):
        keys = ("onset_density", "binary_entropy_bits", "gap_histogram",
                "gap_entropy_bits", "gap_coefficient_of_variation",
                "minimal_period_steps", "canonical_rotation",
                "cyclic_transition_count", "cyclic_onset_overlap_counts")
        for name,p in PATTERNS:
            a = rhythm_metrics(p)
            for i in range(len(p)):
                with self.subTest(name=name, shift=i):
                    b = rhythm_metrics(p[i:]+p[:i])
                    for key in keys:
                        self.assertEqual(a[key], b[key], key)

    def test_reversal_invariance(self):
        for name,p in PATTERNS:
            with self.subTest(name=name):
                a,b = rhythm_metrics(p),rhythm_metrics(p[::-1])
                for key in ("gap_histogram", "gap_entropy_bits", "minimal_period_steps",
                            "cyclic_onset_overlap_counts"):
                    self.assertEqual(a[key], b[key])

    def test_silence_and_full(self):
        a,b = rhythm_metrics("0000"),rhythm_metrics("1111")
        self.assertIsNone(a["gap_entropy_bits"])
        self.assertIsNone(a["gap_mean_steps"])
        self.assertIsNone(a["gap_coefficient_of_variation"])
        self.assertIsNone(a["cyclic_onset_overlap_fraction"])
        self.assertEqual(a["cyclic_onset_overlap_counts"], [0]*4)
        self.assertEqual(b["cyclic_interonset_gaps_steps"], [1]*4)
        self.assertEqual(b["cyclic_onset_overlap_fraction"], [1]*4)
        for m in (a,b):
            self.assertEqual(m["minimal_period_steps"], 1)
            self.assertEqual(m["cyclic_transition_count"], 0)

    def test_single_onset_and_single_step(self):
        m = rhythm_metrics("001000")
        self.assertEqual(m["cyclic_interonset_gaps_steps"], [6])
        self.assertEqual(m["cyclic_onset_overlap_counts"], [1,0,0,0,0,0])
        self.assertEqual(rhythm_metrics("1")["cyclic_interonset_gaps_steps"], [1])
        self.assertEqual(rhythm_metrics("0")["minimal_period_steps"], 1)

    def test_accounting(self):
        for name,p in PATTERNS:
            with self.subTest(name=name):
                m = rhythm_metrics(p)
                n,k = len(p),p.count("1")
                self.assertEqual(sum(m["cyclic_interonset_gaps_steps"]), n if k else 0)
                self.assertEqual(sum(m["cyclic_onset_overlap_counts"]), k*k)
                self.assertEqual(m["cyclic_onset_overlap_counts"][0], k)
                self.assertEqual(m["minimal_period_steps"]*m["repetitions"], n)
                self.assertEqual(m["cyclic_transition_count"] % 2, 0)

    def test_invalid_input(self):
        for p in ("", "012", "a", None, 101):
            with self.subTest(p=p), self.assertRaises(ValueError):
                rhythm_metrics(p)

    def test_cli_repeatability(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main([]), 0)
        self.assertEqual(json.loads(out.getvalue()), rhythm_study())
        self.assertEqual(rhythm_study(), rhythm_study())
