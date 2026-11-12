import unittest
from klone.cognition_metrics import Prediction, brier_score, calibration_bins, benchmark_report


class CognitionMetricsTests(unittest.TestCase):
    def test_perfect_predictions(self):
        data = [Prediction(1.0, True), Prediction(0.0, False)]
        self.assertEqual(brier_score(data), 0.0)
        self.assertEqual(benchmark_report(data)["n"], 2)

    def test_wrong_predictions(self):
        self.assertEqual(brier_score([Prediction(1.0, False)]), 1.0)

    def test_boundaries(self):
        self.assertEqual(len(calibration_bins([Prediction(1.0, True)])), 1)
        with self.assertRaises(ValueError):
            Prediction(float("nan"), True)
        with self.assertRaises(ValueError):
            brier_score([])


if __name__ == "__main__":
    unittest.main()
