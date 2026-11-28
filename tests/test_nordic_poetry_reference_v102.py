import io
import json
import unittest
from contextlib import redirect_stdout

from klone.nordic_poetry_reference import FIXTURES, poetry_reference_demo, main


class NordicPoetryReferenceV102(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = poetry_reference_demo()

    def test_inventory_and_provenance(self):
        self.assertEqual(self.report["example_count"], 12)
        self.assertEqual(self.report["annotation_source"],
                         "assistant_authored_illustrative_examples")
        self.assertIs(self.report["independent_expert_review"], False)

    def test_segmentation_reproduces_text(self):
        for _, line, segmentation in FIXTURES:
            self.assertEqual(segmentation.replace("-", "").casefold(), line.casefold())

    def test_reference_counts(self):
        self.assertEqual([r["reference_syllables"] for r in self.report["examples"]],
                         [3, 4, 4, 4, 4, 4, 4, 4, 5, 6, 5, 7])

    def test_category_errors(self):
        categories = {r["category"]: r for r in self.report["categories"]}
        self.assertEqual(categories["regular"]["difference_histogram"], {"0": 6})
        self.assertEqual(categories["hiatus"]["difference_histogram"], {"-1": 6})

    def test_summary(self):
        r = self.report["summary"]
        self.assertEqual(r["annotated_lines"], 12)
        self.assertEqual(r["exact_count_matches"], 6)
        self.assertEqual(r["exact_match_fraction"], 0.5)
        self.assertEqual(r["mean_absolute_difference"], 0.5)
        self.assertEqual(r["mean_signed_difference"], -0.5)

    def test_cli_repeatability(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main([]), 0)
        self.assertEqual(json.loads(out.getvalue()), self.report)
        self.assertEqual(poetry_reference_demo(), self.report)
