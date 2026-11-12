import unittest
from klone.cognition_sweep import sweep


class SweepTests(unittest.TestCase):
    def test_repeatable(self):
        self.assertEqual(sweep(), sweep())

    def test_zero_rate_matches_baseline(self):
        self.assertEqual(sweep(seeds=(1, 2), rates=(0.0,), steps=8)["results"][0]["mean_improvement"], 0)

    def test_bounds(self):
        with self.assertRaises(ValueError):
            sweep(seeds=(), steps=8)
