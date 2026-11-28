import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

from PIL import Image
from klone.cellular_art import cellular_study, main


class CellularArtV85(unittest.TestCase):
    def test_rule_zero(self):
        r, _ = cellular_study(0, 9, 5)
        self.assertEqual(r["active_counts_per_row"], [1, 0, 0, 0, 0])

    def test_rule_255(self):
        r, _ = cellular_study(255, 9, 5)
        self.assertEqual(r["active_counts_per_row"], [1, 9, 9, 9, 9])

    def test_rule_204_identity(self):
        r, _ = cellular_study(204, 9, 5)
        self.assertEqual(r["active_counts_per_row"], [1] * 5)

    def test_rule_90_triangle(self):
        r, _ = cellular_study(90, 17, 5)
        self.assertEqual(r["active_counts_per_row"], [1, 2, 2, 4, 2])

    def test_rule_30_known_rows(self):
        _, png = cellular_study(30, 7, 3)
        with Image.open(io.BytesIO(png)) as image:
            rows = ["".join("1" if image.getpixel((x, y)) == (234, 184, 86)
                            else "0" for x in range(7)) for y in range(3)]
        self.assertEqual(rows, ["0001000", "0011100", "0110010"])

    def test_periodic_wrap(self):
        r, _ = cellular_study(90, 3, 4)
        self.assertEqual(r["active_counts_per_row"], [1, 2, 2, 2])

    def test_accounting_and_entropy(self):
        for rule in (0, 30, 90, 110, 255):
            r, _ = cellular_study(rule, 17, 9)
            self.assertEqual(r["active_samples"], sum(r["active_counts_per_row"]))
            self.assertEqual(r["total_samples"], 153)
            self.assertTrue(0 <= r["binary_marginal_entropy_bits"] <= 1)
            self.assertEqual(r["active_fraction"], r["active_samples"] / 153)

    def test_repeatable_png(self):
        result = cellular_study(30, 17, 9)
        self.assertEqual(result, cellular_study(30, 17, 9))
        with Image.open(io.BytesIO(result[1])) as image:
            self.assertEqual((image.format, image.size), ("PNG", (17, 9)))
            image.load()

    def test_invalid_parameters(self):
        for args in ((-1, 9, 3), (256, 9, 3), (True, 9, 3),
                     (30, 2, 3), (30, 258, 3), (30, 9, 0), (30, 9, 129)):
            with self.assertRaises(ValueError):
                cellular_study(*args)

    def test_cli_and_exclusive_output(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cells.png"
            args = ["--rule", "90", "--width", "17", "--generations", "9",
                    "--output", str(path)]
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(main(args), 0)
            report, png = cellular_study(90, 17, 9)
            self.assertEqual(json.loads(out.getvalue()), report)
            self.assertEqual(path.read_bytes(), png)
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(args)
            self.assertEqual(path.read_bytes(), png)
