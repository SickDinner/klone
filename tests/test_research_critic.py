from __future__ import annotations

import unittest

from klone.research_compare import ResearchComparison
from klone.research_critic import critique_comparison


class CriticTests(unittest.TestCase):
    def test_changed_citations_need_review(self):
        comparison = ResearchComparison("t", 1, 2, "old", "new",
                                        ("added",), ("removed",), "+new", False)
        result = critique_comparison(comparison)
        self.assertEqual(result.status, "review_needed")
        self.assertTrue(any("manual" in text for text in result.limitations))

    def test_unchanged_does_not_claim_truth(self):
        comparison = ResearchComparison("t", 1, 2, "same", "same",
                                        (), (), "", True)
        result = critique_comparison(comparison)
        self.assertEqual(result.status, "unchanged")
        self.assertTrue(any("correctness" in text for text in result.limitations))


if __name__ == "__main__":
    unittest.main()
