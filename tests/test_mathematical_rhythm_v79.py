import json
import math
import unittest
import xml.etree.ElementTree as ET
from contextlib import redirect_stdout
from io import StringIO

from klone.mathematical_rhythm import rhythm_study, render_rhythm_svg, main


class MathematicalRhythmV79(unittest.TestCase):
    def test_72_eight_pulses(self):
        r = rhythm_study(72, 8)
        self.assertEqual(r["cyclic_gaps_steps"], [9] * 8)
        self.assertEqual(r["fundamental_period_steps"], 9)
        self.assertEqual(r["rotational_repetitions"], 8)

    def test_three_in_eight(self):
        r = rhythm_study(8, 3)
        self.assertEqual(sorted(r["cyclic_gaps_steps"]), [2, 3, 3])
        self.assertEqual(r["fundamental_period_steps"], 8)

    def test_empty_and_full(self):
        self.assertEqual(rhythm_study(8, 0)["cyclic_gaps_steps"], [])
        self.assertEqual(rhythm_study(8, 0)["fundamental_period_steps"], 1)
        self.assertEqual(rhythm_study(8, 8)["cyclic_gaps_steps"], [1] * 8)
        self.assertEqual(rhythm_study(8, 8)["fundamental_period_steps"], 1)

    def test_single_pulse(self):
        self.assertEqual(rhythm_study(72, 1)["cyclic_gaps_steps"], [72])

    def test_all_supported_patterns(self):
        for steps in range(1, 73):
            for pulses in range(steps + 1):
                r = rhythm_study(steps, pulses)
                self.assertEqual(sum(r["pattern"]), pulses)
                self.assertEqual(len(r["pattern"]), steps)
                self.assertEqual(r["fundamental_period_steps"],
                                 steps // math.gcd(steps, pulses))
                if pulses:
                    gaps = r["cyclic_gaps_steps"]
                    self.assertEqual(sum(gaps), steps)
                    self.assertLessEqual(max(gaps) - min(gaps), 1)

    def test_invalid_values(self):
        for steps, pulses in ((0, 0), (73, 1), (8, 9), (8, -1), (True, 1), (8, False)):
            with self.assertRaises(ValueError):
                rhythm_study(steps, pulses)

    def test_svg(self):
        root = ET.fromstring(render_rhythm_svg(72, 8))
        circles = root.findall("{http://www.w3.org/2000/svg}circle")
        self.assertEqual(len(circles), 73)
        self.assertEqual(sum(c.get("fill") == "#f6c76b" for c in circles), 8)

    def test_cli(self):
        output = StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["--steps", "9", "--pulses", "8"]), 0)
        self.assertEqual(json.loads(output.getvalue()), rhythm_study(9, 8))
