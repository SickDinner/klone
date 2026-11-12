import unittest

from klone.cognition_planner import Action, DEFAULT_ACTIONS, plan


class CognitionPlannerTests(unittest.TestCase):
    def test_determinism(self):
        args = dict(energy=0.8, uncertainty=0.7, actions=DEFAULT_ACTIONS)
        self.assertEqual(plan(**args), plan(**args))

    def test_abstention(self):
        result = plan(energy=0.0, uncertainty=0.0, actions=DEFAULT_ACTIONS)
        self.assertEqual(result["actions_executed"], 0)
        self.assertEqual(result["steps"], [])

    def test_no_unaffordable_actions(self):
        result = plan(energy=0.01, uncertainty=1, actions=DEFAULT_ACTIONS)
        self.assertEqual(result["steps"], [])

    def test_bounds(self):
        with self.assertRaises(ValueError):
            plan(energy=0.5, uncertainty=0.5, actions=DEFAULT_ACTIONS, horizon=100)
        with self.assertRaises(ValueError):
            plan(energy=float("nan"), uncertainty=0.5, actions=DEFAULT_ACTIONS)
        with self.assertRaises(ValueError):
            Action("bad", 0, 0, float("inf"))


if __name__ == "__main__":
    unittest.main()
