import unittest
from klone.cognition_neurocortex import CortexConfig, run_cortex, compare_cortex, NAMES


class NeuroCortexTests(unittest.TestCase):
    def test_deterministic(self):
        c = CortexConfig(steps=20)
        self.assertEqual(run_cortex(c), run_cortex(c))

    def test_all_six_modulators(self):
        r = run_cortex(CortexConfig(steps=3, snapshot_interval=1))
        self.assertEqual(set(r["snapshots"][0]["vertical_slice"]["modulators"]), set(NAMES))

    def test_hash_chain(self):
        r = run_cortex(CortexConfig(steps=12))
        self.assertEqual(r["deltas"][0]["previous_hash"], "0" * 64)
        for a, b in zip(r["deltas"], r["deltas"][1:]):
            self.assertEqual(a["state_hash"], b["previous_hash"])
        self.assertEqual(r["trace_root"], r["deltas"][-1]["state_hash"])

    def test_compare(self):
        r = compare_cortex(CortexConfig(steps=10))
        self.assertEqual(len(r["modulated"]["deltas"]), 10)
        self.assertEqual(len(r["unmodulated"]["deltas"]), 10)

    def test_bounds(self):
        for args in ({"steps": 0}, {"steps": 501},
                     {"learning_rate": float("nan")}, {"snapshot_interval": 0}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                CortexConfig(**args)
