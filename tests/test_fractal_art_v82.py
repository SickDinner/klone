import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

from PIL import Image
from klone.fractal_art import escape_count, fractal_study, main
from klone.artwork_color_metrics import artwork_color_metrics


class FractalArtV82(unittest.TestCase):
    def test_known_points(self):
        self.assertIsNone(escape_count(0, 0, 48))
        self.assertIsNone(escape_count(-1, 0, 48))
        self.assertEqual(escape_count(3, 0, 48), 1)
        self.assertEqual(escape_count(2, 0, 48), 2)

    def test_sample_accounting(self):
        report, _ = fractal_study(32, 24)
        self.assertEqual(report["escaped_samples"] + report["unresolved_samples"], 1024)
        self.assertEqual(sum(report["escape_histogram"].values()), report["escaped_samples"])
        self.assertEqual(report["unresolved_fraction"], report["unresolved_samples"] / 1024)

    def test_iteration_limit(self):
        low, _ = fractal_study(32, 4)
        high, _ = fractal_study(32, 48)
        self.assertLess(high["unresolved_samples"], low["unresolved_samples"])
        self.assertTrue(all(int(k) <= 48 for k in high["escape_histogram"]))

    def test_conjugate_symmetry(self):
        for real, imag in ((-.75, .2), (.5, .5), (-1.5, .4)):
            self.assertEqual(escape_count(real, imag, 48), escape_count(real, -imag, 48))

    def test_png_and_determinism(self):
        r, png = fractal_study(32, 24)
        self.assertEqual((r, png), fractal_study(32, 24))
        with Image.open(io.BytesIO(png)) as image:
            self.assertEqual((image.format, image.mode, image.size), ("PNG", "RGB", (32, 32)))
            image.load()

    def test_invalid_bounds(self):
        for size, iterations in ((15, 48), (257, 48), (32, 0), (32, 97), (True, 48), (32, 4.0)):
            with self.assertRaises(ValueError):
                fractal_study(size, iterations)

    def test_existing_palette_analysis(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fractal.png"
            _, png = fractal_study(32, 24)
            path.write_bytes(png)
            report = artwork_color_metrics(path, full_histogram=True)
            self.assertGreater(report["occupied_rgb_bins"], 1)
            self.assertEqual(report["full_histogram"]["sample_pixels"], 1024)
            self.assertEqual(path.read_bytes(), png)

    def test_cli_and_exclusive_output(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fractal.png"
            args = ["--size", "16", "--iterations", "12", "--output", str(path)]
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(args), 0)
            report, png = fractal_study(16, 12)
            self.assertEqual(json.loads(output.getvalue()), report)
            self.assertEqual(path.read_bytes(), png)
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(args)
            self.assertEqual(path.read_bytes(), png)
