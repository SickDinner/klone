import unittest
from klone.cognition_learning import LearningConfig, compare_learning, run_learning


class CognitionLearningTests(unittest.TestCase):
    def test_determinism(self):
        c = LearningConfig(steps=64, seed=72)
        self.assertEqual(compare_learning(c), compare_learning(c))

    def test_ablation_is_constant(self):
        r = run_learning(LearningConfig(steps=8), learn=False)
        self.assertEqual(r["final_prediction"], 0.5)
        self.assertEqual(len(r["trace"]), 8)

    def test_bounds(self):
        for args in ({"steps": 0}, {"steps": 501}, {"seed": -1},
                     {"learning_rate": float("nan")},
                     {"initial_prediction": float("inf")}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                LearningConfig(**args)

    def test_no_claim(self):
        self.assertFalse(run_learning(LearningConfig(steps=2))["consciousness_measure"])
