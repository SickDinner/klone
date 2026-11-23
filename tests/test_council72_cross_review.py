"""Acceptance tests for the non-authoritative 9x8 / 8x9 cross-review overlay."""
import unittest
from copy import deepcopy

from klone.cognition_neurocortex import NAMES
from klone.council72 import AUTHORITY, catalog, deliberate, demo_proposal
from klone.council72_cross_review import cross_review, cross_review_replays


class CrossReviewTests(unittest.TestCase):
    def setUp(self):
        self.model = catalog()
        self.round = deliberate(demo_proposal())

    def test_two_views_cover_exactly_the_same_72_members(self):
        report = cross_review(self.round)
        self.assertEqual(report["topology"]["unique_members"], 72)
        self.assertEqual(len(report["ring_views"]), 9)
        self.assertEqual(len(report["founder_line_views"]), 8)
        self.assertEqual(report["cross_checks"]["specialist_cells_evaluated"], 64)
        rings = report["ring_views"]
        lines = report["founder_line_views"]
        self.assertEqual([len(x["member_ids"]) for x in rings], [8] * 9)
        self.assertEqual([len(x["member_ids"]) for x in lines], [9] * 8)
        self.assertEqual({m for line in lines for m in line["member_ids"]}, set(range(1, 73)))
        for ring_index, ring in enumerate(rings):
            for col, member_id in enumerate(ring["member_ids"]):
                self.assertEqual(lines[col]["member_ids"][ring_index], member_id)
        self.assertEqual([line["founder_id"] for line in lines],
                         self.model["founder_ids"])

    def test_deterministic_replay_and_round_tampering_rejected(self):
        a = cross_review(self.round)
        b = cross_review(self.round)
        self.assertEqual(a, b)
        self.assertTrue(cross_review_replays(self.round, a))
        modified = deepcopy(a)
        modified["advisory"]["changes_base_decision"] = True
        self.assertFalse(cross_review_replays(self.round, modified))
        tampered_round = deepcopy(self.round)
        tampered_round["opinions"][0]["vote"] = "oppose"
        with self.assertRaises(ValueError):
            cross_review(tampered_round)

    def test_simulated_and_explicit_founder_ballots_are_not_conflated(self):
        proposal = demo_proposal()
        proposal["founder_votes"] = {
            str(member_id): "endorse" for member_id in self.model["founder_ids"]
        }
        proposal["founder_votes"][str(self.model["founder_ids"][0])] = "oppose"
        round_report = deliberate(proposal)
        report = cross_review(round_report)
        first = report["founder_line_views"][0]
        self.assertEqual(first["founder_vote_source"], "explicit_input")
        self.assertEqual(first["member_ids"][-1], self.model["founder_ids"][0])
        self.assertGreaterEqual(first["votes"]["oppose"], 1)
        self.assertEqual(report["advisory"]["base_decision_status"], "contested")

    def test_sources_not_counted_twice_by_repeated_views(self):
        proposal = demo_proposal()
        proposal["ring_evidence"] = {
            str(i): ["same-unverified-reference"] for i in range(1, 9)
        }
        report = cross_review(deliberate(proposal))
        self.assertEqual(report["evidence"]["references_total"], 8)
        self.assertEqual(report["evidence"]["unique_reference_strings"], 1)
        self.assertFalse(report["evidence"]["authenticated"])
        self.assertFalse(report["evidence"]["independent_sources_verified"])
        self.assertTrue(report["advisory"]["human_review_required"])
        self.assertFalse(report["advisory"]["autonomous_release_allowed"])
        self.assertFalse(report["advisory"]["changes_base_decision"])
        for key in AUTHORITY:
            self.assertFalse(report[key])

    def test_strong_ring_vs_line_split_creates_review_flag(self):
        good = {"evidence_quality": 1.0, "uncertainty": 0.0,
                "risk": 0.0, "novelty": 1.0, "reward": 1.0,
                "threat": 0.0, "social_feedback": 1.0}
        bad = {"evidence_quality": 0.0, "uncertainty": 1.0,
               "risk": 1.0, "novelty": 0.0, "reward": 0.0,
               "threat": 1.0, "social_feedback": 0.0}
        context = {
            "member_modulators": {
                str(m["id"]): {name: 0.5 for name in NAMES}
                for m in self.model["members"]
            },
            "ring_signals": {
                str(i): (good if i == 2 else bad) for i in range(1, 9)
            },
        }
        round_report = deliberate(demo_proposal(), context=context)
        report = cross_review(round_report)
        self.assertGreater(report["cross_checks"]["conflict_count"], 0)
        self.assertEqual(report["advisory"]["status"], "cross_review_required")
        self.assertTrue(any(c["ring_id"] == 2
                            for c in report["cross_checks"]["conflicts"]))
        self.assertTrue(cross_review_replays(round_report, report))


if __name__ == "__main__":
    unittest.main()
