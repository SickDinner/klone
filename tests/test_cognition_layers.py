import unittest
from klone.cognition_layers import probe_layers


class LayerProbeTests(unittest.TestCase):
    def test_repeatable(self):
        self.assertEqual(probe_layers([0.2, 0.4]), probe_layers([0.2, 0.4]))

    def test_shapes(self):
        r = probe_layers([0.5])
        self.assertEqual([len(x["activations"]) for x in r["layers"]], [8, 8, 4])
        self.assertFalse(r["actual_llm_instrumented"])

    def test_nonfinite(self):
        with self.assertRaises(ValueError):
            probe_layers([float("nan")])
