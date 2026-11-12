import unittest

from klone.cognition_experiment_lab import (
    council_72, compare_agent_strategies, examine_claim,
    falsification_plan, neurochemical_policy,
)


class CognitionExperimentLabTests(unittest.TestCase):
    def test_neurochemical_inhibition_limits_exploration(self):
        active = neurochemical_policy(dopamine=1, noradrenaline=0,
                                      acetylcholine=0, inhibition=0)
        blocked = neurochemical_policy(dopamine=1, noradrenaline=0,
                                       acetylcholine=0, inhibition=1)
        self.assertEqual(active["novelty"], 1)
        self.assertEqual(blocked["novelty"], 0)
        self.assertEqual(blocked["mode"], "review")

    def test_neurochemical_invalid_range(self):
        with self.assertRaises(ValueError):
            neurochemical_policy(dopamine=2, noradrenaline=0,
                                 acetylcholine=0, inhibition=0)

    def test_counterevidence_prevents_uncontested_claim(self):
        result = examine_claim(claim_id="claim:1", supporting=["a"],
                               contradicting=["b"], independent_sources=2)
        self.assertEqual(result["verdict"], "contested")
        self.assertTrue(result["human_review_required"])

    def test_duplicate_evidence_rejected(self):
        with self.assertRaises(ValueError):
            examine_claim(claim_id="x", supporting=["a"],
                          contradicting=["a"], independent_sources=1)

    def test_falsification_threshold_is_inclusive(self):
        result = falsification_plan(hypothesis="A improves B", metric="accuracy",
                                    reject_if_at_or_below=0.7, observed=0.7)
        self.assertEqual(result["outcome"], "rejected")
        self.assertFalse(result["proves_hypothesis"])

    def test_agent_ranking_is_deterministic(self):
        agents = [
            {"name": "b", "accuracy": 0.8, "hallucination_rate": 0.1,
             "resource_cost": 0.2},
            {"name": "a", "accuracy": 0.8, "hallucination_rate": 0.1,
             "resource_cost": 0.2},
        ]
        self.assertEqual([x["name"] for x in
                          compare_agent_strategies(agents)["ranking"]], ["a", "b"])

    def test_council_is_advisory_even_with_unanimity(self):
        votes = dict.fromkeys(range(1, 73), "yes")
        result = council_72(votes, proposal_id="proposal:1")
        self.assertTrue(result["advisory_consensus"])
        self.assertFalse(result["binding_authority"])
        self.assertFalse(result["deployment_approval"])
        self.assertEqual(len(result["rings"]), 9)

    def test_council_requires_all_nodes(self):
        with self.assertRaises(ValueError):
            council_72({1: "yes"}, proposal_id="proposal:1")
